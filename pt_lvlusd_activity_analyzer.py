"""
PT-slvlUSD Activity Analyzer - Focused on Recent Sellers and Buyers
Tracks wallets that:
1. Had PT-slvlUSD activity (buy/sell) in last 60 days
2. Bought any tokens recently

Requirements:
- requests
- pandas
- Free Etherscan API key

Usage:
    python pt_lvlusd_activity_analyzer.py
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import json
import csv
import os
from typing import List, Dict, Optional
import logging

class PTSlvlUSDActivityAnalyzer:
    def __init__(self, etherscan_api_key: str):
        self.etherscan_api_key = etherscan_api_key
        self.etherscan_base = "https://api.etherscan.io/v2/api"
        self.rate_limit_delay = 0.2  # 5 requests per second for free tier
        
        # PT-slvlUSD contract address
        self.pt_slvlusd_contract = "0x2CA5f2C4300450D53214B00546795c1c07B89acB"
        
        # Major token contracts for buy activity analysis
        self.major_tokens = {
            'usdc': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            'usdt': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'eth': 'native',  # Native ETH (handled separately in balance checks)
            'pt-slvlusd': '0x2CA5f2C4300450D53214B00546795c1c07B89acB',
            # 'pt-slvlusd': '0x2CA5f2C4300450D53214B00546795c1c07B89acB'
        }

        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def get_pt_slvlusd_activity_last_60_days(self) -> List[Dict]:
        """Get wallets that had PT-slvlUSD activity (buy/sell) in the last 60 days using Etherscan API V2"""
        active_wallets = {}
        start_time = int((datetime.now() - timedelta(days=120)).timestamp())
        
        # Fetch multiple pages to get more transactions
        all_transactions = []
        page = 1
        max_pages = 100  # Significantly increased to get much more data
        
        while page <= max_pages:
            params = {
                'chainid': 1,  # Ethereum mainnet
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': self.pt_slvlusd_contract,
                'page': page,
                'offset': 10000,  # Get more transactions per page
                'sort': 'desc',
                'apikey': self.etherscan_api_key
            }

            response = requests.get(self.etherscan_base, params=params)
            data = response.json()
            
            if page == 1:
                self.logger.info(f"Etherscan API V2 response status: {data.get('status')} - Message: {data.get('message')}")
            
            if data['status'] == '1' and data['result']:
                transactions = data['result']
                all_transactions.extend(transactions)
                self.logger.info(f"Fetched {len(transactions)} transactions from page {page}")
                
                # If we got less than the offset, we've reached the end
                if len(transactions) < 10000:
                    break
                    
                page += 1
                time.sleep(self.rate_limit_delay)  # Rate limiting between pages
            else:
                self.logger.error(f"Etherscan API V2 error on page {page}: {data.get('message', 'Unknown error')} - Status: {data.get('status', 'Unknown')}")
                break

        if all_transactions:
            self.logger.info(f"Total transactions fetched: {len(all_transactions)}")
            
            for tx in all_transactions:
                tx_time = int(tx['timeStamp'])
                # Include both buyers and sellers (any wallet activity)
                if tx_time >= start_time:
                    from_addr = tx['from'].lower()
                    to_addr = tx['to'].lower()
                    amount = float(tx['value']) / (10 ** int(tx['tokenDecimal']))
                    
                    # Track sellers (from address)
                    if from_addr != '0x0000000000000000000000000000000000000000':
                        if from_addr not in active_wallets:
                            active_wallets[from_addr] = {
                                'address': from_addr,
                                'total_sold': 0,
                                'total_bought': 0,
                                'transaction_count': 0,
                                'first_activity': tx_time,
                                'last_activity': tx_time
                            }
                        active_wallets[from_addr]['total_sold'] += amount
                        active_wallets[from_addr]['transaction_count'] += 1
                        
                    # Track buyers (to address)
                    if to_addr != '0x0000000000000000000000000000000000000000':
                        if to_addr not in active_wallets:
                            active_wallets[to_addr] = {
                                'address': to_addr,
                                'total_sold': 0,
                                'total_bought': 0,
                                'transaction_count': 0,
                                'first_activity': tx_time,
                                'last_activity': tx_time
                            }
                        active_wallets[to_addr]['total_bought'] += amount
                        active_wallets[to_addr]['transaction_count'] += 1
                        
                    # Update activity times for both
                    for addr in [from_addr, to_addr]:
                        if addr in active_wallets:
                            if tx_time < active_wallets[addr]['first_activity']:
                                active_wallets[addr]['first_activity'] = tx_time
                            if tx_time > active_wallets[addr]['last_activity']:
                                active_wallets[addr]['last_activity'] = tx_time
                    
            self.logger.info(f"Found {len(active_wallets)} unique PT-slvlUSD active wallets via Etherscan API V2")
        else:
            self.logger.error("No transaction data retrieved")
            return []
        
        # Convert to list and sort by total activity (sold + bought)
        wallet_list = list(active_wallets.values())
        wallet_list.sort(key=lambda x: x['total_sold'] + x['total_bought'], reverse=True)
        
        return wallet_list

    def check_recent_token_buys(self, wallet_address: str, days: int = 30) -> Dict:
        """Check if wallet bought any major tokens in last N days"""
        buy_activity = {
            'total_buys': 0,
            'tokens_bought': [],
            'total_value_estimate': 0,
            'most_recent_buy': None
        }
        
        start_time = int((datetime.now() - timedelta(days=days)).timestamp())
        
        # Check each major token for buy activity (skip ETH as it's handled separately)
        for token_name, contract_address in self.major_tokens.items():
            if token_name == 'eth':  # Skip ETH - native transactions handled separately
                continue
                
            try:
                params = {
                    'chainid': 1,  # Ethereum mainnet
                    'module': 'account',
                    'action': 'tokentx',
                    'contractaddress': contract_address,
                    'address': wallet_address,
                    'startblock': 0,
                    'endblock': 99999999,
                    'sort': 'desc',
                    'apikey': self.etherscan_api_key
                }

                response = requests.get(self.etherscan_base, params=params)
                time.sleep(self.rate_limit_delay)
                
                data = response.json()
                
                if data['status'] == '1' and data['result']:
                    recent_buys = []
                    for tx in data['result']:
                        tx_time = int(tx['timeStamp'])
                        if tx_time >= start_time and tx['to'].lower() == wallet_address.lower():
                            # This is a buy (incoming transaction)
                            amount = float(tx['value']) / 1e18
                            recent_buys.append({
                                'token': token_name,
                                'amount': amount,
                                'timestamp': tx_time,
                                'hash': tx['hash']
                            })
                    
                    if recent_buys:
                        buy_activity['total_buys'] += len(recent_buys)
                        buy_activity['tokens_bought'].extend(recent_buys)
                        
                        # Estimate USD value (rough)
                        for buy in recent_buys:
                            if token_name in ['usdc', 'usdt']:
                                buy_activity['total_value_estimate'] += buy['amount']
                            elif token_name in ['pt-lvlusd', 'pt-slvlusd']:
                                buy_activity['total_value_estimate'] += buy['amount'] * 2500  # Rough ETH price
                        
                        # Track most recent buy
                        latest_buy = max(recent_buys, key=lambda x: x['timestamp'])
                        if not buy_activity['most_recent_buy'] or latest_buy['timestamp'] > buy_activity['most_recent_buy']['timestamp']:
                            buy_activity['most_recent_buy'] = latest_buy
                            
            except Exception as e:
                self.logger.error(f"Error checking {token_name} buys for {wallet_address}: {e}")
                # Continue with other tokens
                continue
        
        return buy_activity

    def get_wallet_current_balances(self, wallet_address: str) -> Dict:
        """Get current token balances for wallet"""
        balances = {}
        
        # Get ETH balance
        try:
            params = {
                'chainid': 1,  # Ethereum mainnet
                'module': 'account',
                'action': 'balance',
                'address': wallet_address,
                'tag': 'latest',
                'apikey': self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_base, params=params)
            data = response.json()
            
            if data['status'] == '1':
                balances['eth'] = float(data['result']) / 1e18
            else:
                balances['eth'] = 0
                
        except Exception as e:
            self.logger.error(f"Error getting ETH balance for {wallet_address}: {e}")
            balances['eth'] = 0
        
        time.sleep(self.rate_limit_delay)
        
        # Get token balances (skip ETH as it's already handled above)
        for token_name, contract_address in self.major_tokens.items():
            if token_name == 'eth':  # Skip ETH - already handled above
                continue
                
            try:
                params = {
                    'chainid': 1,  # Ethereum mainnet
                    'module': 'account',
                    'action': 'tokenbalance',
                    'contractaddress': contract_address,
                    'address': wallet_address,
                    'tag': 'latest',
                    'apikey': self.etherscan_api_key
                }
                
                response = requests.get(self.etherscan_base, params=params)
                data = response.json()
                
                if data['status'] == '1':
                    # Different decimals for different tokens
                    if token_name in ['usdc', 'usdt']:
                        balances[token_name] = float(data['result']) / 1e6
                    else:
                        balances[token_name] = float(data['result']) / 1e18
                else:
                    balances[token_name] = 0
                    
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                self.logger.error(f"Error getting {token_name} balance for {wallet_address}: {e}")
                balances[token_name] = 0
        
        return balances

    def calculate_activity_score(self, seller_data: Dict, buy_activity: Dict, balances: Dict) -> int:
        """Calculate activity score based on selling PT-slvlUSD and buying other tokens"""
        score = 0
        
        # PT-lvlUSD selling activity (0-40 points)
        sell_count = seller_data.get('sell_count', 0)
        total_sold = seller_data.get('total_sold', 0)
        
        if sell_count >= 3:
            score += 20
        elif sell_count >= 1:
            score += 10
            
        if total_sold >= 1000:
            score += 20
        elif total_sold >= 100:
            score += 15
        elif total_sold >= 10:
            score += 10
        
        # Recent buy activity (0-30 points)
        total_buys = buy_activity.get('total_buys', 0)
        if total_buys >= 5:
            score += 30
        elif total_buys >= 3:
            score += 20
        elif total_buys >= 1:
            score += 10
        
        # Portfolio value (0-30 points)
        portfolio_value = (
            balances.get('usdc', 0) +
            balances.get('usdt', 0) +
            balances.get('eth', 0) * 2500  # ETH at ~$2500
        )
        
        if portfolio_value >= 50000:
            score += 30
        elif portfolio_value >= 10000:
            score += 25
        elif portfolio_value >= 1000:
            score += 15
        elif portfolio_value >= 100:
            score += 10
        
        return min(score, 100)  # Cap at 100

    def analyze_pt_slvlusd_activity(self, max_wallets = None) -> List[Dict]:
        """Main analysis function"""
        self.logger.info("Starting PT-slvlUSD activity analysis...")
        
        # Step 1: Get PT-slvlUSD active wallets
        active_wallets = self.get_pt_slvlusd_activity_last_60_days()
        self.logger.info(f"Found {len(active_wallets)} PT-slvlUSD active wallets")
        
        if len(active_wallets) < 50:
            self.logger.warning(f"Only found {len(active_wallets)} active wallets, which is less than expected. Consider increasing the time range or checking API limits.")
        
        # Step 2: Analyze each active wallet
        results = []
        if max_wallets is None:
            actual_max = len(active_wallets)
            print(f"📊 Found {len(active_wallets)} unique PT-lvlUSD active wallets, analyzing ALL wallets")
        else:
            actual_max = min(len(active_wallets), max_wallets)
            print(f"📊 Found {len(active_wallets)} unique PT-lvlUSD active wallets, analyzing up to {actual_max} wallets")
        
        for i, wallet_data in enumerate(active_wallets[:actual_max], 1):
            wallet_address = wallet_data['address']
            self.logger.info(f"Analyzing wallet {i}/{actual_max}: {wallet_address}")
            
            # Check recent buy activity (30 days)
            buy_activity = self.check_recent_token_buys(wallet_address, days=30)
            
            # Get current balances
            balances = self.get_wallet_current_balances(wallet_address)
            
            # Calculate activity score
            activity_score = self.calculate_activity_score(wallet_data, buy_activity, balances)
            
            # Classify the wallet
            if activity_score >= 80:
                classification = "High-activity seller/buyer"
            elif activity_score >= 60:
                classification = "Active seller/buyer"
            elif activity_score >= 40:
                classification = "Moderate activity"
            elif activity_score >= 20:
                classification = "Low activity"
            else:
                classification = "Minimal activity"
            
            result = {
                'wallet_address': wallet_address,
                'pt_slvlusd_sold': wallet_data.get('total_sold', 0),
                'pt_slvlusd_bought': wallet_data.get('total_bought', 0),
                'sell_transactions': wallet_data.get('transaction_count', 0),
                'recent_token_buys': buy_activity['total_buys'],
                'buy_value_estimate': buy_activity['total_value_estimate'],
                'tokens_bought': [buy['token'] for buy in buy_activity['tokens_bought']],
                'current_balances': balances,
                'activity_score': activity_score,
                'classification': classification,
                'most_recent_buy': buy_activity.get('most_recent_buy')
            }
            
            results.append(result)
            
            # Rate limiting
            time.sleep(self.rate_limit_delay * 2)
            
            if i % 10 == 0:
                self.logger.info(f"Completed {i}/{actual_max} wallets")
        
        return results

    def export_results(self, results: List[Dict], filename: str = None):
        """Export analysis results to CSV"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pt_slvlusd_activity_analysis_{timestamp}.csv"
        
        csv_data = []
        
        for result in results:
            balances = result['current_balances']
            
            # Format current holdings
            holdings_parts = []
            if balances.get('usdc', 0) > 0:
                holdings_parts.append(f"${balances['usdc']:.0f} USDC")
            if balances.get('usdt', 0) > 0:
                holdings_parts.append(f"${balances['usdt']:.0f} USDT")
            if balances.get('eth', 0) > 0:
                holdings_parts.append(f"{balances['eth']:.2f} ETH")
            if balances.get('pt-slvlusd', 0) > 0:
                holdings_parts.append(f"{balances['pt-slvlusd']:.0f} PT-slvlUSD")
            if balances.get('pt-slvlusd', 0) > 0:
                holdings_parts.append(f"{balances['pt-slvlusd']:.0f} PT-slvlUSD")
            
            holdings_str = " + ".join(holdings_parts) if holdings_parts else "No significant holdings"
            
            # Format tokens bought
            tokens_bought_str = ", ".join(set(result['tokens_bought'])) if result['tokens_bought'] else "None"
            
            csv_row = {
                'Wallet Address': result['wallet_address'],
                'PT-slvlUSD Sold (60 days)': f"{result['pt_slvlusd_sold']:.2f}",
                'Sell Transactions': result['sell_transactions'],
                'Recent Token Buys (30 days)': result['recent_token_buys'],
                'Buy Value Estimate': f"${result['buy_value_estimate']:.0f}",
                'Tokens Bought': tokens_bought_str,
                'Current Holdings': holdings_str,
                'Activity Score': f"{result['activity_score']}/100",
                'Classification': result['classification']
            }
            
            csv_data.append(csv_row)
        
        # Sort by activity score
        csv_data.sort(key=lambda x: int(x['Activity Score'].split('/')[0]), reverse=True)
        
        # Save to CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(filename, index=False)
        
        print(f"\n✅ Analysis complete! Results saved to {filename}")
        print(f"📊 Analyzed {len(csv_data)} wallets")
        print(f"🏆 Top 3 activity scores: {[row['Activity Score'] for row in csv_data[:3]]}")
        
        # Show sample results
        print(f"\n📋 TOP PROSPECTS:")
        print("-" * 100)
        for i, row in enumerate(csv_data[:3]):
            print(f"{i+1}. {row['Wallet Address']}")
            print(f"   Sold: {row['PT-slvlUSD Sold (60 days)']} PT-slvlUSD | Recent buys: {row['Recent Token Buys (30 days)']}") 
            print(f"   Holdings: {row['Current Holdings']}")
            print(f"   {row['Classification']} ({row['Activity Score']})")
            print()
        
        return filename

def main():
    """Main execution function"""
    print("=== PT-SLVLUSD ACTIVITY ANALYZER ===\n")
    print("Tracking wallets that:")
    print("1. 📈 Had PT-slvlUSD activity (buy/sell) in last 60 days")
    print("2. 🛒 Bought any tokens recently")
    print()
    
    # Configuration
    config = {
        "etherscan_api_key": os.getenv("ETHERSCAN_API_KEY", "UZHTPZ6HB2VN7APKHX97UKMDGCFUJNRE2X"),  # Use env var or replace with your real API key
        "max_wallets": 500,  # Analyze up to 500 wallet addresses
        "output_file": "pt_slvlusd_activity_results_60days.csv"
    }
    
    # Initialize analyzer
    analyzer = PTSlvlUSDActivityAnalyzer(config["etherscan_api_key"])
    
    # Run analysis
    print(f"🚀 Starting analysis...")
    if config['max_wallets'] is None:
        print(f"📊 Will analyze ALL discovered wallet addresses")
    else:
        print(f"📊 Will analyze up to {config['max_wallets']} wallets")
    print(f"📅 Looking for PT-slvlUSD activity + token buys in last 60 days")
    print(f"🔍 Fetching comprehensive transaction data from multiple pages...")
    print()
    
    results = analyzer.analyze_pt_slvlusd_activity(max_wallets=config["max_wallets"])
    
    # Export results
    if results:
        analyzer.export_results(results, config["output_file"])
    else:
        print("❌ No results to export.")

if __name__ == "__main__":
    main()