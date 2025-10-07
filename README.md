# YieldFi Wallet Analyzer

Complete solution for finding potential buyers for YieldFi onchain sales using **FREE** tools:
- Etherscan Free API (100k requests/day)
- Dune Analytics Free Plan (unlimited queries)

## 🚀 Quick Start

### 1. Setup (5 minutes)
```bash
# Install requirements
pip install requests pandas

# Get free Etherscan API key
# Visit: https://etherscan.io/apis
```

### 2. Update Configuration
Edit `yieldfi_analyzer.py`:
```python
# Update your API key
"etherscan_api_key": "YOUR_ACTUAL_API_KEY_HERE"

# Update token contract addresses
"pt-usdc": "0xYOUR_PT_USDC_CONTRACT_ADDRESS",
"vyeth": "0xYOUR_VYETH_CONTRACT_ADDRESS"
```

### 3. Run Analysis
```bash
python yieldfi_analyzer.py
```

## 📊 Two Analysis Methods

### Method 1: Python + Etherscan API
- **Pros**: Automated, detailed analysis, multi-token balances
- **Cons**: Rate limited (5 req/sec), needs API key
- **Best for**: Comprehensive wallet analysis

### Method 2: Dune Analytics SQL
- **Pros**: Fast, unlimited queries, no API key needed
- **Cons**: Requires manual query execution
- **Best for**: Quick large-scale analysis

## 📈 Output Format
```csv
Wallet Address,Purchase Times,Total Volume,Current Holdings,Risk Score,Risk Classification
0x742c0f85...,3 buys in last 30 days,$1500 in recent activity,$2500 USDC + 1.2 ETH + 200 pt-usdc + 987 vyeth,85/100,High-value active trader
```

## 🔧 Customization

### Analysis Parameters
- `analysis_days`: Look-back period (default: 30 days)
- `max_wallets`: Number of wallets to analyze (default: 50)
- `min_token_balance`: Minimum token holding threshold

### Risk Scoring Algorithm
- **Recent Activity** (0-30 points): Based on buy frequency
- **Volume Score** (0-25 points): Based on total purchase amount
- **Holdings Value** (0-25 points): USD value of current portfolio
- **Diversity Score** (0-20 points): Number of different tokens held

## 📋 Files Included

- `yieldfi_analyzer.py` - Main Python analyzer
- `yieldfi_dune_query.sql` - Dune Analytics query
- `README.md` - This instructions file

## 💡 Pro Tips

1. **Start Small**: Test with 50 wallets first
2. **Update Prices**: Modify ETH price estimates in scoring algorithm
3. **Filter Results**: Focus on wallets with 60+ risk scores
4. **Combine Methods**: Use Dune for discovery, Python for detailed analysis

## 🆓 Cost Breakdown
- **Data Collection**: $0 (free APIs)
- **Analysis**: $0 (local processing) 
- **Messaging**: ~$1 per wallet (DeBank attention fees)
- **Total for 100 prospects**: ~$100 (messaging only)

## 🔍 Finding More Targets

### Additional Free Sources:
- **Etherscan Token Pages**: Manual holder lists
- **DexScreener**: Recent trader addresses
- **Token Sniffer**: Whale tracking
- **CoinGecko**: Trending token holders

### Advanced Filtering:
- Remove exchange cold wallets
- Filter by wallet age (avoid new wallets)
- Check social media presence (ENS names)
- Verify recent DeFi activity

## ⚠️ Important Notes

1. **Update Contract Addresses**: Must add actual PT-USDC and vyETH addresses
2. **Rate Limiting**: Respect free API limits (100k/day Etherscan)
3. **Privacy**: Only use public blockchain data
4. **Compliance**: Follow platform messaging guidelines

## 🎯 Expected Results

From 1 hour of analysis:
- **500-1000 wallet addresses**
- **Filtered by recent activity and holdings**
- **Risk scored and classified**
- **Ready for outreach campaigns**

Perfect for YieldFi's targeted onchain sale marketing! 🚀
