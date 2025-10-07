
"""
YieldFi Wallet Analyzer - Complete Implementation
Free crypto wallet finder using Etherscan API and Dune Analytics

Requirements:
- requests
- pandas
- Free Etherscan API key (etherscan.io)

Usage:
    python yieldfi_analyzer.py
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import json
import csv
from typing import List, Dict, Optional
import logging

class WalletAnalyzer:
    def __init__(self, etherscan_api_key: str):
        self.etherscan_api_key = etherscan_api_key
        self.etherscan_base = "https://api.etherscan.io/api"
        self.rate_limit_delay = 0.2  # 5 requests per second for free tier

        # Token addresses mapping (UPDATE THESE!)
        self.token_contracts = {
            'PT-lvlUSD-25SEP2025' : '0x207F7205fd6c4b602Fa792C8b2B60e6006D4a0b8',
            # Standard tokens and lowercase mappings
            'pt-lvlusd-25sep2025': '0x207F7205fd6c4b602Fa792C8b2B60e6006D4a0b8',
            'usdc': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # Standard USDC
            'eth': 'ETH'
        }

        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def get_token_contract_address(self, token_symbol: str) -> Optional[str]:
        """Get contract address for token symbol"""
        return self.token_contracts.get(token_symbol.lower())

    def get_manual_holders_for_testing(self) -> List[Dict]:
        """Manual holder list extracted from PT-lvlUSD CSV exports"""
        # Real addresses extracted from PT-lvlUSD transfer data
        manual_addresses = [
            "0xd9147bD9e9466036BC2897747BCe3C9e13463090",  # notairtonjunior.eth
            "0x1fEcD2E54648476bD6AeA2f5B8BBD5155166816e",  # Real PT-lvlUSD trader
            "0x93c318E595F58E4Ffc8779E35E574832D8d9a5Dc",  # Real PT-lvlUSD trader
            "0x5EBe5223831523823528Ef0a7EdF67D288B1B070",  # mempoolwarrior.eth
            "0x5D6cE4B1067430e240DDfC0f2f2c18511C8E837d",  # Real PT-lvlUSD trader
            "0x461bc2ac3f80801BC11B0F20d63B73feF60C8076",  # Pendle PENDLE-LPT Token 175
            "0x0f298efdc63c607f8d530f0d0f38c1b431443f13",  # Known working address
            "0x3e89cc4d0edf5777ac84e07fb1898caa6fbb19b4",  # Known working address
            "0xb95e0d975775d0af74dbf8153f5c7a7484e4d023",  # Known working address
            "0x577aff6ddad1d25ee18fee16de7037de44f2f5e8",  # Known working address
        ]
        
        holders_list = []
        for address in manual_addresses:
            holders_list.append({
                'TokenHolderAddress': address,
                'TokenHolderQuantity': '0'
            })
        
        self.logger.info(f"Using manual holder list: {len(holders_list)} addresses")
        return holders_list

    def get_token_holders_from_transfers(self, contract_address: str, max_pages: int = 10) -> List[Dict]:
        """Get token holders by analyzing recent transfer events (Free API compatible)"""
        unique_holders = set()
        holders_list = []

        for page in range(1, max_pages + 1):
            # Use token transfer events to find active wallets
            params = {
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': contract_address,
                'page': page,
                'offset': 1000,  # Get more transfers per request
                'sort': 'asc',  # Try oldest first to get more historical data
                'apikey': self.etherscan_api_key
            }

            try:
                response = requests.get(self.etherscan_base, params=params)
                response.raise_for_status()
                data = response.json()

                if data['status'] == '1' and data['result']:
                    for tx in data['result']:
                        # Add both sender and receiver to our holder list
                        for address in [tx['to'], tx['from']]:
                            if address not in unique_holders and address != '0x0000000000000000000000000000000000000000':
                                unique_holders.add(address)
                                holders_list.append({
                                    'TokenHolderAddress': address,
                                    'TokenHolderQuantity': '0'  # We'll get actual balance later
                                })
                    
                    self.logger.info(f"Fetched page {page}: Found {len(data['result'])} transfers, {len(unique_holders)} unique addresses")
                    time.sleep(self.rate_limit_delay)
                    
                    # Stop if we have enough unique addresses
                    if len(unique_holders) >= 1000:
                        break
                else:
                    self.logger.warning(f"No more transfer data available at page {page}")
                    break

            except Exception as e:
                self.logger.error(f"Error fetching transfers page {page}: {e}")
                break

        self.logger.info(f"Total unique holders found: {len(holders_list)}")
        return holders_list

    def get_wallet_transactions(self, wallet_address: str, contract_address: str, days: int = 30) -> List[Dict]:
        """Get wallet transactions for specific token in last N days"""
        start_time = int((datetime.now() - timedelta(days=days)).timestamp())

        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': contract_address,
            'address': wallet_address,
            'startblock': 0,
            'endblock': 99999999,
            'sort': 'desc',
            'apikey': self.etherscan_api_key
        }

        try:
            response = requests.get(self.etherscan_base, params=params)
            response.raise_for_status()
            data = response.json()

            if data['status'] == '1':
                recent_txs = [tx for tx in data['result'] 
                            if int(tx['timeStamp']) >= start_time]
                return recent_txs
            return []

        except Exception as e:
            self.logger.error(f"Error fetching transactions for {wallet_address}: {e}")
            return []

    def get_multiple_token_balances(self, wallet_address: str, token_symbols: List[str]) -> Dict[str, float]:
        """Get balances for multiple tokens for a wallet"""
        balances = {}

        for symbol in token_symbols:
            contract_address = self.get_token_contract_address(symbol)

            if symbol.lower() == 'eth':
                balance = self.get_eth_balance(wallet_address)
                balances[symbol] = balance
            elif contract_address and contract_address != '0x':
                balance = self.get_token_balance(wallet_address, contract_address)
                balances[symbol] = balance
            else:
                balances[symbol] = 0

            time.sleep(self.rate_limit_delay)

        return balances

    def get_eth_balance(self, wallet_address: str) -> float:
        """Get ETH balance for wallet"""
        params = {
            'module': 'account',
            'action': 'balance',
            'address': wallet_address,
            'tag': 'latest',
            'apikey': self.etherscan_api_key
        }

        try:
            response = requests.get(self.etherscan_base, params=params)
            data = response.json()

            if data['status'] == '1':
                return float(data['result']) / 1e18
            return 0

        except Exception as e:
            self.logger.error(f"Error fetching ETH balance for {wallet_address}: {e}")
            return 0

    def get_token_balance(self, wallet_address: str, contract_address: str) -> float:
        """Get token balance for wallet"""
        params = {
            'module': 'account',
            'action': 'tokenbalance',
            'contractaddress': contract_address,
            'address': wallet_address,
            'tag': 'latest',
            'apikey': self.etherscan_api_key
        }

        try:
            response = requests.get(self.etherscan_base, params=params)
            data = response.json()

            if data['status'] == '1':
                return float(data['result']) / 1e18
            return 0

        except Exception as e:
            self.logger.error(f"Error fetching token balance for {wallet_address}: {e}")
            return 0

    def calculate_risk_score(self, wallet_data: Dict) -> tuple:
        """Calculate risk score and classification"""
        score = 0

        # Recent activity score (0-30 points)
        buy_count = wallet_data.get('buy_count', 0)
        if buy_count >= 5:
            score += 30
        elif buy_count >= 3:
            score += 20
        elif buy_count >= 1:
            score += 10

        # Total volume score (0-25 points)
        total_volume = wallet_data.get('total_volume_usd', 0)
        if total_volume >= 10000:
            score += 25
        elif total_volume >= 5000:
            score += 20
        elif total_volume >= 1000:
            score += 15
        elif total_volume >= 100:
            score += 10

        # Holdings diversity score (0-25 points)
        balances = wallet_data.get('current_holdings', {})
        non_zero_holdings = len([v for v in balances.values() if v > 0])
        if non_zero_holdings >= 4:
            score += 25
        elif non_zero_holdings >= 3:
            score += 20
        elif non_zero_holdings >= 2:
            score += 15
        elif non_zero_holdings >= 1:
            score += 10

        # Holdings value score (0-20 points)
        estimated_usd_value = (
            balances.get('usdc', 0) +
            balances.get('eth', 0) * 2500 +  # Approximate ETH price
            balances.get('pt-usdc', 0) +
            balances.get('vyeth', 0) * 2500
        )

        if estimated_usd_value >= 50000:
            score += 20
        elif estimated_usd_value >= 10000:
            score += 15
        elif estimated_usd_value >= 1000:
            score += 10
        elif estimated_usd_value >= 100:
            score += 5

        # Determine classification
        if score >= 80:
            classification = "High-value, active trader"
        elif score >= 60:
            classification = "Active trader"
        elif score >= 40:
            classification = "Moderate activity"
        elif score >= 20:
            classification = "Low activity"
        else:
            classification = "Minimal activity"

        return score, classification

    def analyze_wallet_portfolio(self, wallet_address: str, target_tokens: List[str], 
                                analysis_days: int = 30) -> Dict:
        """Complete analysis of a wallet"""
        result = {
            'wallet_address': wallet_address,
            'buy_count': 0,
            'total_volume_usd': 0,
            'current_holdings': {},
            'purchase_history': [],
            'risk_score': 0,
            'risk_classification': 'Unknown'
        }

        try:
            # Get current balances for all target tokens
            result['current_holdings'] = self.get_multiple_token_balances(wallet_address, target_tokens)

            # Analyze transaction history for the main target token
            main_token = target_tokens[0] if target_tokens else 'usdc'
            contract_address = self.get_token_contract_address(main_token)

            if contract_address and contract_address != '0x':
                transactions = self.get_wallet_transactions(wallet_address, contract_address, analysis_days)

                buy_transactions = []
                total_volume = 0

                for tx in transactions:
                    if tx['to'].lower() == wallet_address.lower():  # Incoming = buy
                        value_tokens = float(tx['value']) / 1e18
                        buy_transactions.append({
                            'timestamp': datetime.fromtimestamp(int(tx['timeStamp'])),
                            'amount': value_tokens,
                            'tx_hash': tx['hash']
                        })
                        total_volume += value_tokens

                result['buy_count'] = len(buy_transactions)
                result['total_volume_usd'] = total_volume
                result['purchase_history'] = buy_transactions

            # Calculate risk score
            score, classification = self.calculate_risk_score(result)
            result['risk_score'] = score
            result['risk_classification'] = classification

        except Exception as e:
            self.logger.error(f"Error analyzing wallet {wallet_address}: {e}")

        return result

    def process_wallets_batch(self, target_tokens: List[str], target_tokens_list: List[str], 
                             max_wallets: int = 100, analysis_days: int = 30) -> List[Dict]:
        """Process a batch of wallets for analysis from multiple tokens"""
        all_unique_holders = set()
        holders_list = []

        # Fetch holders from ALL your target tokens
        for token in target_tokens:
            contract_address = self.get_token_contract_address(token)
            
            if not contract_address or contract_address == '0x':
                self.logger.warning(f"Skipping invalid contract address for token: {token}")
                continue

            self.logger.info(f"Fetching holders for {token}...")
            
            # TEMPORARY: Use manual holders due to API deprecation
            if token == "pt-lvlusd-25sep2025":
                token_holders = self.get_manual_holders_for_testing()
            else:
                token_holders = self.get_token_holders_from_transfers(contract_address, max_pages=10)
            
            # Add unique holders to our master list
            for holder in token_holders:
                address = holder['TokenHolderAddress']
                if address not in all_unique_holders:
                    all_unique_holders.add(address)
                    holders_list.append(holder)
                    
            self.logger.info(f"Found {len(token_holders)} holders for {token}, total unique: {len(all_unique_holders)}")

        # Limit to max_wallets
        holders = holders_list[:max_wallets]

        results = []
        total_holders = len(holders)

        self.logger.info(f"Analyzing {total_holders} wallets...")

        for i, holder in enumerate(holders, 1):
            wallet_address = holder['TokenHolderAddress']

            self.logger.info(f"Processing wallet {i}/{total_holders}: {wallet_address}")

            # Analyze this wallet
            analysis = self.analyze_wallet_portfolio(wallet_address, target_tokens_list, analysis_days)
            results.append(analysis)

            # Rate limiting
            time.sleep(self.rate_limit_delay * 2)

            # Progress update every 10 wallets
            if i % 10 == 0:
                self.logger.info(f"Completed {i}/{total_holders} wallets")

        return results

    def export_to_csv(self, analysis_results: List[Dict], filename: str = 'wallet_analysis.csv'):
        """Export results to CSV with exact format requested"""
        if not analysis_results:
            self.logger.warning("No results to export")
            return

        csv_data = []

        for result in analysis_results:
            # Format holdings string exactly as requested
            holdings_parts = []
            holdings = result['current_holdings']

            if holdings.get('usdc', 0) > 0:
                holdings_parts.append(f"${holdings['usdc']:.0f} USDC")
            if holdings.get('eth', 0) > 0:
                holdings_parts.append(f"{holdings['eth']:.1f} ETH")
            if holdings.get('pt-lvlusd-25sep2025', 0) > 0:
                holdings_parts.append(f"{holdings['pt-lvlusd-25sep2025']:.0f} PT-lvlUSD")

            holdings_str = " + ".join(holdings_parts) if holdings_parts else "No significant holdings"

            # Format exactly as requested in example
            csv_row = {
                'Wallet Address': result['wallet_address'],
                'Purchase Times': f"{result['buy_count']} buys in last 30 days",
                'Total Volume': f"${result['total_volume_usd']:.0f} in recent activity",
                'Current Holdings': holdings_str,
                'Risk Score': f"{result['risk_score']}/100",
                'Risk Classification': result['risk_classification']
            }

            csv_data.append(csv_row)

        # Sort by risk score descending
        csv_data.sort(key=lambda x: int(x['Risk Score'].split('/')[0]), reverse=True)

        # Write to CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(filename, index=False)

        self.logger.info(f"Results exported to {filename}")
        print(f"\n✅ Analysis complete! Results saved to {filename}")
        print(f"📊 Analyzed {len(csv_data)} wallets")
        print(f"🏆 Top 3 risk scores: {[row['Risk Score'] for row in csv_data[:3]]}")

        # Show sample results
        print(f"\n📋 SAMPLE RESULTS:")
        print("-" * 100)
        for i, row in enumerate(csv_data[:3]):
            print(f"{i+1}. {row['Wallet Address']}")
            print(f"   {row['Purchase Times']} | {row['Total Volume']}")
            print(f"   {row['Current Holdings']}")
            print(f"   {row['Risk Classification']} ({row['Risk Score']})")
            print()

        return filename

def main():
    """Main execution function"""
    print("=== YIELDFI WALLET ANALYZER ===\n")

    # Configuration
    config = {
        "etherscan_api_key": "UZHTPZ6HB2VN7APKHX97UKMDGCFUJNRE2X",  # UPDATE THIS!
        "target_tokens": ["pt-lvlusd-25sep2025"],  # Only PT-lvlUSD token
        "analysis_tokens": ["pt-lvlusd-25sep2025", "usdc", "eth"],
        "max_wallets": 100,
        "analysis_days": 30,
        "output_file": "pt_lvlusd_prospects.csv"
    }

    # Validate API key
    if config["etherscan_api_key"] == "YOUR_ETHERSCAN_API_KEY_HERE":
        print("❌ Please update your Etherscan API key in the config!")
        print("📋 Get your free API key at: https://etherscan.io/apis")
        return

    # Initialize analyzer
    analyzer = WalletAnalyzer(config["etherscan_api_key"])

    # Update contract addresses (YOU NEED TO DO THIS!)
    print("⚠️  IMPORTANT: Update contract addresses in the code for:")
    print("   - pt-usdc contract address")
    print("   - vyeth contract address")
    print()

    # Run analysis
    print(f"🚀 Starting analysis for ALL your tokens:")
    for token in config["target_tokens"]:
        print(f"   - {token}")
    print(f"📊 Will analyze up to {config['max_wallets']} unique wallets")
    print(f"📅 Looking at last {config['analysis_days']} days")
    print()

    results = analyzer.process_wallets_batch(
        target_tokens=config["target_tokens"],
        target_tokens_list=config["analysis_tokens"],
        max_wallets=config["max_wallets"],
        analysis_days=config["analysis_days"]
    )

    # Export results
    if results:
        analyzer.export_to_csv(results, config["output_file"])
    else:
        print("❌ No results to export. Check your token contract addresses.")

if __name__ == "__main__":
    main()
