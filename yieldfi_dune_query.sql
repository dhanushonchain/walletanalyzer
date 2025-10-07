-- YIELDFI WALLET FINDER: Dune Analytics Query
-- Copy this entire query to dune.com and run it
-- Update the token addresses below for your specific tokens

-- CONFIGURATION: Update these token addresses
-- PT-USDC Token Address: UPDATE THIS!
-- vyETH Token Address: UPDATE THIS!
-- Analysis period: 30 days (adjust as needed)

WITH target_tokens AS (
  SELECT '0x' as pt_usdc_address,  -- UPDATE: Add actual PT-USDC contract address
         '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48' as usdc_address,
         '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2' as weth_address,
         '0x' as vyeth_address  -- UPDATE: Add actual vyETH contract address
),

-- Find recent buyers in last 30 days
recent_pt_usdc_buyers AS (
    SELECT DISTINCT
        t."to" as wallet_address,
        COUNT(*) as buy_count,
        SUM(t.value / 1e18) as total_pt_usdc_bought,
        MAX(t.evt_block_time) as last_buy_time,
        MIN(t.evt_block_time) as first_buy_time
    FROM erc20_ethereum.evt_Transfer t
    CROSS JOIN target_tokens tt
    WHERE t.contract_address = tt.pt_usdc_address  -- Update this address!
        AND t.evt_block_time >= now() - interval '30' day
        AND t."to" != '0x0000000000000000000000000000000000000000'
        AND t."from" != '0x0000000000000000000000000000000000000000'
        AND t.value / 1e18 >= 1  -- Minimum 1 token purchase
    GROUP BY t."to"
    HAVING COUNT(*) >= 1
),

-- Get current token balances for these wallets
wallet_balances AS (
    SELECT 
        b.wallet_address,
        -- PT-USDC balance
        SUM(CASE 
            WHEN b.token_address = (SELECT pt_usdc_address FROM target_tokens)
            THEN b.amount_raw / 1e18 
            ELSE 0 
        END) as pt_usdc_balance,
        -- USDC balance  
        SUM(CASE 
            WHEN b.token_address = (SELECT usdc_address FROM target_tokens)
            THEN b.amount_raw / 1e6 
            ELSE 0 
        END) as usdc_balance,
        -- WETH balance
        SUM(CASE 
            WHEN b.token_address = (SELECT weth_address FROM target_tokens)
            THEN b.amount_raw / 1e18 
            ELSE 0 
        END) as weth_balance,
        -- vyETH balance
        SUM(CASE 
            WHEN b.token_address = (SELECT vyeth_address FROM target_tokens)
            THEN b.amount_raw / 1e18 
            ELSE 0 
        END) as vyeth_balance
    FROM tokens_ethereum.balances_latest b
    WHERE b.wallet_address IN (SELECT wallet_address FROM recent_pt_usdc_buyers)
    GROUP BY b.wallet_address
),

-- Get ETH balances
eth_balances AS (
    SELECT 
        address as wallet_address,
        balance / 1e18 as eth_balance
    FROM ethereum.balances_latest
    WHERE address IN (SELECT wallet_address FROM recent_pt_usdc_buyers)
),

-- Get current ETH price for USD calculations
current_eth_price AS (
    SELECT price as eth_usd_price
    FROM prices.usd 
    WHERE contract_address = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
        AND minute >= now() - interval '2' hour
    ORDER BY minute DESC
    LIMIT 1
),

-- Combine all data and calculate scores
final_analysis AS (
    SELECT 
        rb.wallet_address,
        rb.buy_count,
        rb.total_pt_usdc_bought,
        rb.last_buy_time,
        rb.first_buy_time,

        -- Balances
        COALESCE(wb.pt_usdc_balance, 0) as pt_usdc_balance,
        COALESCE(wb.usdc_balance, 0) as usdc_balance,
        COALESCE(eb.eth_balance, 0) as eth_balance,
        COALESCE(wb.weth_balance, 0) as weth_balance,
        COALESCE(wb.vyeth_balance, 0) as vyeth_balance,

        -- USD values
        (COALESCE(wb.usdc_balance, 0) + 
         (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) * cep.eth_usd_price) as total_stable_value_usd,

        -- Risk scoring (0-100)
        (
            -- Recent activity score (0-30)
            CASE 
                WHEN rb.buy_count >= 5 THEN 30
                WHEN rb.buy_count >= 3 THEN 20  
                WHEN rb.buy_count >= 1 THEN 10
                ELSE 0 
            END +

            -- Volume score (0-25)  
            CASE 
                WHEN rb.total_pt_usdc_bought >= 10000 THEN 25
                WHEN rb.total_pt_usdc_bought >= 5000 THEN 20
                WHEN rb.total_pt_usdc_bought >= 1000 THEN 15
                WHEN rb.total_pt_usdc_bought >= 100 THEN 10
                ELSE 0 
            END +

            -- Holdings value score (0-25)
            CASE 
                WHEN (COALESCE(wb.usdc_balance, 0) + (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) * cep.eth_usd_price) >= 50000 THEN 25
                WHEN (COALESCE(wb.usdc_balance, 0) + (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) * cep.eth_usd_price) >= 10000 THEN 20
                WHEN (COALESCE(wb.usdc_balance, 0) + (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) * cep.eth_usd_price) >= 1000 THEN 15
                WHEN (COALESCE(wb.usdc_balance, 0) + (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) * cep.eth_usd_price) >= 100 THEN 10
                ELSE 0 
            END +

            -- Portfolio diversity score (0-20)
            CASE 
                WHEN (CASE WHEN COALESCE(wb.pt_usdc_balance, 0) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN COALESCE(wb.usdc_balance, 0) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN COALESCE(wb.vyeth_balance, 0) > 0 THEN 1 ELSE 0 END) >= 4 THEN 20
                WHEN (CASE WHEN COALESCE(wb.pt_usdc_balance, 0) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN COALESCE(wb.usdc_balance, 0) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN COALESCE(wb.vyeth_balance, 0) > 0 THEN 1 ELSE 0 END) >= 3 THEN 15
                WHEN (CASE WHEN COALESCE(wb.pt_usdc_balance, 0) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN COALESCE(wb.usdc_balance, 0) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN (COALESCE(eb.eth_balance, 0) + COALESCE(wb.weth_balance, 0)) > 0 THEN 1 ELSE 0 END +
                      CASE WHEN COALESCE(wb.vyeth_balance, 0) > 0 THEN 1 ELSE 0 END) >= 2 THEN 10
                ELSE 5 
            END
        ) as risk_score

    FROM recent_pt_usdc_buyers rb
    LEFT JOIN wallet_balances wb ON rb.wallet_address = wb.wallet_address
    LEFT JOIN eth_balances eb ON rb.wallet_address = eb.wallet_address
    CROSS JOIN current_eth_price cep
)

-- Final output with exact format requested
SELECT 
    wallet_address as "Wallet Address",

    buy_count || ' buys in last 30 days' as "Purchase Times",

    '$' || ROUND(total_pt_usdc_bought, 0) || ' in recent activity' as "Total Volume",

    -- Format holdings exactly as requested
    TRIM(BOTH ' + ' FROM 
        CASE WHEN usdc_balance > 0 THEN '$' || ROUND(usdc_balance, 0) || ' USDC + ' ELSE '' END ||
        CASE WHEN (eth_balance + weth_balance) > 0 THEN ROUND(eth_balance + weth_balance, 1) || ' ETH + ' ELSE '' END ||
        CASE WHEN pt_usdc_balance > 0 THEN ROUND(pt_usdc_balance, 0) || ' pt-usdc + ' ELSE '' END ||
        CASE WHEN vyeth_balance > 0 THEN ROUND(vyeth_balance, 0) || ' vyeth + ' ELSE '' END
    ) as "Current Holdings",

    risk_score || '/100' as "Risk Score",

    CASE 
        WHEN risk_score >= 80 THEN 'High-value, active trader'
        WHEN risk_score >= 60 THEN 'Active trader'
        WHEN risk_score >= 40 THEN 'Moderate activity' 
        WHEN risk_score >= 20 THEN 'Low activity'
        ELSE 'Minimal activity'
    END as "Risk Classification",

    -- Additional data for analysis
    buy_count,
    ROUND(total_pt_usdc_bought, 2) as total_bought,
    ROUND(total_stable_value_usd, 2) as portfolio_usd_value,
    last_buy_time

FROM final_analysis
WHERE total_stable_value_usd >= 50  -- Minimum $50 portfolio value
ORDER BY risk_score DESC, total_pt_usdc_bought DESC
LIMIT 500;

-- Query Instructions:
-- 1. Update the token addresses in the target_tokens CTE at the top
-- 2. Run this query on dune.com (free account)
-- 3. Export results as CSV
-- 4. Use the CSV for your YieldFi outreach campaign
