# Thesis figures and tables

Figures and tables as printed in the thesis, in thesis numbering. Tables are exported as CSV. `analysis/thesis/run.py` recomputes them into `output/thesis/`.

## Figures

**Figure 1: [Projected global warming in the IPCC AR6 scenarios](figures/fig01_projected_global_warming_in_the_ipcc_ar6.png)**  
Source: own processing based on IPCC (2021, Table SPM.1). Note: best estimates with very likely ranges, relative to 1850–1900. The dashed line marks the observed 1.55 °C of 2024 (WMO, 2025), the dotted line 1.5 °C.

**Figure 2: [How a solid-sorbent DACCS plant works](figures/fig02_how_a_solid_sorbent_daccs_plant_works.png)**  
Source: own processing. Energy use per tonne: working values of this thesis (Section 2.5).

**Figure 3: [Schematic merit order of the Czech zone in two hours](figures/fig03_schematic_merit_order_of_the_czech_zone_in.png)**  
Source: own processing based on ENTSO-E generation data for 2024 and OTE prices. Note: the width of each block is the highest hourly output of the source in 2024, and the minimum load of lignite is its lowest hourly output in 2024. The heights show only the order of the bids, not estimated costs. The two lines mark the total Czech generation in the two hours of Table 1.

**Figure 4: [Czech generation mix and negative prices by hour of day, April–August 2024–2025](figures/fig04_czech_generation_mix_and_negative_prices_by.png)**  
Source: own computation from ENTSO-E generation and load data and OTE prices. Note: mean output by source and hour (upper panel) and share of hours with a negative day-ahead price (lower panel), local time.

**Figure 5: [Negative-price hours on the Czech day-ahead market](figures/fig05_negative_price_hours_on_the_czech_day_ahead.png)**  
Source: own computation from OTE data.

**Figure 6: [Simulated negative-price hours per year in the solar scenarios](figures/fig06_simulated_negative_price_hours_per_year_in.png)**  
Source: own computation (Chapter 6). Note: mean over the simulated paths with the 5–95 % interval. The scenarios scale Czech solar infeed by 1.6, 2.1 and 2.6 for 2030 and 3.0 for 2035, the joint variant also scales German solar along § 4 EEG 2023.

**Figure 7: [EU allowance price and DACCS removal-credit prices](figures/fig07_eu_allowance_price_and_daccs_removal_credit.png)**  
Source: own processing based on Nissen et al. (2025) and ESMA (2026) for the EUA and CDR.fyi and OPIS (2025) for DACCS credits. Note: credit prices converted at 0.88 EUR/USD. No public time series of durable removal-credit prices exists, so the survey values for 2025 and the suppliers’ expectation for 2030 are shown.

**Figure 8: [Carbon dioxide removal by method in 2023](figures/fig08_carbon_dioxide_removal_by_method_in_2023.png)**  
Source: own processing based on Smith et al. (2024, Chapter 7). Note: logarithmic scale. Conventional removal is the managed-land estimate based on national inventories.

**Figure 9: [Length of blocks of consecutive negative-price hours, 2020–2025](figures/fig09_length_of_blocks_of_consecutive_negative.png)**  
Source: own computation from OTE data. Note: (a) number of blocks of each length, (b) negative-price hours in blocks of each length, 213 blocks and 931 hours in total.

**Figure 10: [Day-ahead price and residual load by sub-period](figures/fig10_day_ahead_price_and_residual_load_by_sub.png)**  
Source: own computation from OTE prices and ČEPS load and infeed. Note: one point per hour, r is the correlation coefficient. The vertical axes differ between the panels.

**Figure 11: [The three-layer pipeline: Each layer uses the output of the previous one](figures/fig11_the_three_layer_pipeline_each_layer_uses_the.png)**  
Source: own processing.

**Figure 12: [Layer A: steps of the econometric analysis](figures/fig12_layer_a_steps_of_the_econometric_analysis.png)**  
Source: own processing.

**Figure 13: [Layer B: steps of the operating analysis](figures/fig13_layer_b_steps_of_the_operating_analysis.png)**  
Source: own processing.

**Figure 14: [Layer C: steps of the economic analysis](figures/fig14_layer_c_steps_of_the_economic_analysis.png)**  
Source: own processing.

## Tables

**Table 1: [Generation, cross-border flows and price in two hours of 2024 (MW)](tables/tab01_generation_cross_border_flows_and_price_in.csv)**  
Source: own computation from ENTSO-E generation and load data, ČEPS cross-border flows and pumped-storage load, and OTE and ENTSO-E prices. Note: local time. Hydro includes pumped-storage generation. A positive net import flows into the Czech zone. Generation plus net import minus pumping equals load up to differences between the sources.

**Table 2: [Carbon-removal methods compared: storage, cost and EU certification](tables/tab02_carbon_removal_methods_compared_storage_cost.csv)**  
Source: Fuss et al. (2018, Table 2) for storage and literature cost (the authors’ assessment, full literature ranges are wider), CDR.fyi and OPIS (2025) for supplier break-evens (averaged survey results), European Union (2024) and European Commission (2026) for certification. Note: Mineralisation (316 / 228 US$/t) is a heterogeneous category not assessed by Fuss et al. (2018) and is therefore not listed.

**Table 3: [Data sources](tables/tab03_data_sources.csv)**  
Source: own processing.

**Table 4: [Czech day-ahead price by year (EUR/MWh) and negative-price hours](tables/tab04_czech_day_ahead_price_by_year_eur_mwh_and.csv)**  
Source: own computation from the merged panel (OTE prices, ČEPS solar infeed).

**Table 5: [Neighbouring zones of the Czech Republic in 2025: price coupling and physical flows](tables/tab05_neighbouring_zones_of_the_czech_republic_in.csv)**  
Source: own computation from ENTSO-E day-ahead prices and ČEPS cross-border physical flows. Note: Germany is the sum of the TenneT and 50Hertz borders. A positive flow enters the Czech zone. Physical flows include transit, so they show where electricity moves, not who sold it.

**Table 6: [Emission factors and generation shares of Czech power sources, 2024](tables/tab06_emission_factors_and_generation_shares_of.csv)**  
Source: own computation from ENTSO-E generation data. Note: direct emissions per MWh of electricity as used in the model. Other fossil: gas 0.36, oil 0.65, hard coal 0.87, coal-derived gas 1.40. Biomass counts as zero, waste 0.26, other 0.30.

**Table 7: [Emission factor of delivered heat by allocation convention (tCO₂/MWhₜₕ)](tables/tab07_emission_factor_of_delivered_heat_by.csv)**  
Source: own computation, combustion factors from IPCC (2006). Note: η el and η th are the electrical and heat efficiencies, heat is delivered at 90–95 °C. For a boiler the three conventions coincide. Where the fuel would burn anyway (waste under a disposal obligation), the marginal factor is zero.
