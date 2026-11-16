# International Cost of Capital

A Streamlit app for comparing nominal USD and target-currency project discount rates. Defaults: Software (System & Application), United States, US project tax, 6.5% ERP, 30% debt.

## Run or deploy
1. Create a public GitHub repository (e.g. `international-cost-of-capital`). Upload `app.py`, `requirements.txt`, `README.md` and optionally `test_model.py` to its root and commit.
2. Visit https://share.streamlit.io/ and sign in with GitHub. Create an app, choose the repository, branch `main`, and main file `app.py`. Deploy. No API key is required.
3. Locally: `python -m pip install -r requirements.txt` then `python -m streamlit run app.py`. Run `python -m unittest test_model.py` for checks.

## Data
- [Damodaran US industry betas workbook](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls), with [HTML alternative](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html). Uses **unlevered beta**, not cash-adjusted beta.
- [Damodaran ratings](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html): first Baa2/BBB spread for large non-financial service firms.
- [OECD corporate tax database](https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html): SDMX dataset version 2.0, latest available annual combined statutory general-government rate by jurisdiction. Not effective tax.
- [Trading Economics bonds](https://tradingeconomics.com/bonds): country-specific 10-year government bond pages and bonds table. Quote dates are labeled unknown if not parsed; retrieval timestamp is separate.

Refresh invalidates cached fetches. Failed fetches explicitly show dated reference data (limited industry and tax subsets; US yield only) or missing values. For unsupported countries or blocked pages, enter missing values manually. The app does not invent local data. Country list is ISO-based; not every country publishes a 10-year yield or an OECD tax rate. Country currency label is editable. Public HTML can change; the network fetches and final UI must be tested after deployment, as this development environment has no outbound network. Reference beta and spread are January 2026; reference tax rates are 2025; US yield reference is 5.146% on November 16, 2026. These are not live data.

## Formula assumptions — confirm with instructor
Class formulas were not supplied. Default provisional method is gross-rate parity, with an alternative Local CAPM mode to use the exact same numerical ERP across currencies. In both, D/E = debt share/(1−debt share), levered beta = unlevered beta × [1+(1−tax)×D/E], USD Ke = US yield + levered beta × ERP, USD Kd = US yield + USD spread. Under parity, F=(1+local yield)/(1+US yield), local Ke=(1+USD Ke)×F−1 and auto local spread=USD spread×F. Under Local CAPM, local Ke=local yield+levered beta×ERP and auto local spread=USD spread. Local Kd=local yield+local spread (manual override if enabled). WACC=(1−debt share)×Ke+debt share×Kd×(1−tax). Rates are decimals internally. Government yields are proxies, not necessarily default-free; no separate sovereign risk or FX basis adjustment. The same tax rate is applied to both currencies. A selected-industry beta override affects only that industry's comparison row.

## Independent verification example (illustrative inputs, not live)
Unlevered beta 1.23, tax 25.57%, debt 30%, ERP 6.5%, US yield 5%, target yield 3%, USD spread 1.11%, parity mode, no foreign override. Independent decimal arithmetic gives:

| Metric | USD | Target |
|---|---:|---:|
| Levered beta | 1.62235243 | 1.62235243 |
| Cost of equity | 15.545291% | 13.344428% |
| Pre-tax debt cost | 6.110000% | 4.088857% |
| WACC | 12.246005% | 10.254101% |

Spreadsheet formulas for independent reproduction: enter B2:B8 = 1.23, 25.57%, 30%, 6.5%, 5%, 3%, 1.11%. B9 `=B2*(1+(1-B3)*B4/(1-B4))`; B10 `=B6+B9*B5`; B11 `=B6+B8`; B12 `=(1-B4)*B10+B4*B11*(1-B3)`; B13 `=(1+B7)/(1+B6)`; B14 `=(1+B10)*B13-1`; B15 `=B7+B8*B13`; B16 `=(1-B4)*B14+B4*B15*(1-B3)`.

Tests cover the independent numerical example, equal yields, zero debt, and USD invariance under local spread override, in both methods where applicable. Verify the professor's equations and check live source outputs before submission.
