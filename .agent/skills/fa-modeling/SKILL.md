---
name: fa-modeling
description: "Core financial modeling skill. Contains standards and patterns for building institutional-quality DCF (Discounted Cash Flow), LBO, and Comps models. Use when users need to value a company, request intrinsic value analysis, or ask for detailed financial modeling with growth projections."
---

# Financial Modeling (fa-modeling)

## Overview
This skill creates institutional-quality financial models (DCF, Comps) for equity valuation following investment banking standards.

## Critical Constraints - Read These First

**Formulas Over Hardcodes (NON-NEGOTIABLE):**
- Every projection, margin, discount factor, PV, and sensitivity cell MUST be a live formula — never a value computed in Python/LLM and written as a static number.
- The only hardcoded numbers permitted are: (1) raw historical inputs, (2) assumption drivers (growth rates, WACC inputs, terminal g), (3) current market data (share price, debt balance).

**Sensitivity Tables:**
- Use an ODD number of rows and columns (standard: 5×5) — this guarantees a true center cell.
- Center cell = base case.
- Populate ALL cells with full recalculation formulas. NO placeholder text, NO linear approximations.

**Cell Comments:**
- Add cell comments AS each hardcoded value is created.
- Format: "Source: [System/Document], [Date], [Reference]"

## DCF Process Workflow

### Step 1: Historical Analysis (3-5 years)
Analyze and document Revenue growth trends, Margin progression (Gross, EBIT, FCF), Capital intensity (CapEx % of Rev), and Return metrics.

### Step 2: Build Revenue Projections
Use a Three-scenario approach:
- Bear Case: Conservative growth
- Base Case: Most likely scenario
- Bull Case: Optimistic growth
Formula: `Revenue(Year N) = Revenue(Year N-1) × (1 + Growth Rate)`

### Step 3: Operating Expense Modeling
Model operating leverage: S&M, R&D, G&A as a % of revenue. Margins should expand or contract logically based on scale. Calculate `EBIT = Gross Profit - Total OpEx`.

### Step 4: Free Cash Flow Calculation
```
EBIT
(-) Taxes (EBIT × Tax Rate)
= NOPAT
(+) D&A
(-) CapEx
(-) Δ NWC
= Unlevered Free Cash Flow
```

### Step 5: Cost of Capital (WACC) & Discounting
`Cost of Equity = Risk-Free Rate + Beta × Equity Risk Premium`
Calculate WACC using market value weights.
Discount Period (Mid-Year): 0.5, 1.5, 2.5...
`Discount Factor = 1 / (1 + WACC)^Period`

### Step 6: Terminal Value & Equity Bridge
Use Perpetuity Growth Method (`Terminal FCF / (WACC - Terminal Growth Rate)`). Terminal Growth < WACC.
```
Sum of PV of FCFs + PV of Terminal Value = Enterprise Value
Enterprise Value - Net Debt = Equity Value
Equity Value / Diluted Shares = Implied Price per Share
```

## Scenario Block Selection Pattern
Create separate blocks for Bear/Base/Bull cases. Use an INDEX/OFFSET consolidation column controlled by a scenario selector (1=Bear, 2=Base, 3=Bull) to feed the main projection formulas, rather than embedding complex IF statements everywhere.
