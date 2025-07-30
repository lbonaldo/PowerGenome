"""
Load fuel prices needed for the model
"""

import logging
from typing import Dict, List
from powergenome.settings import get_current_settings, NoSettingsError
from pathlib import Path

import pandas as pd

from powergenome.eia_opendata import add_user_fuel_prices

logger = logging.getLogger(__name__)


def fuel_cost_table(
    fuel_costs: pd.DataFrame,
    generators: pd.DataFrame,
    model_year: int = None,
    fuel_emission_factors: dict = None,
    fuel_scenarios: dict = None,
    user_fuel_price: dict = None,
    ccs_fuel_map: dict = None,
    co2_pipeline_filters: bool = None,
    co2_pipeline_cost_fn: str = None,
    ccs_disposal_cost: float = None,
    ccs_capture_rate: dict = None,
    carbon_tax: float = None,
    reduce_time_domain: bool = None,
    time_domain_days_per_period: int = None,
    time_domain_periods: int = None,
    target_usd_year: int = None,
    user_fuel_usd_year: dict = None,
    data_location: Path = None,
    dollar_year_table: str = None,
    num_hours: int = None,
) -> pd.DataFrame:
    """Create a table of fuel costs formatted for the GenX model.

    Costs are based on the `fuel_costs` dataframe and any values listed in the settings
    dictionary under the key "user_fuel_price". If CCS fuels or a carbon tax are defined
    in the settings then the

    Parameters
    ----------
    fuel_costs : pd.DataFrame
        A table of fuel prices. Must have columns "year", "price", "fuel", "region", and
        "full_fuel_name". "fuel" should be a base fuel name such as coal or distillate and
        cannot include an underscore. If the full fuel name is a combination of the region,
        a scenario, and the base fuel name, the base fuel name should be the last element
        so that it is selected when the string is split on underscores.

        >>> <full_fuel_name>.split("_")[-1] = <fuel>
    generators : pd.DataFrame
        A table of generators with the column "Fuel". The values in this column should
        correspond to either the "full_fuel_name" column or one of the fuels in the
        settings key "user_fuel_price". If regional prices are provided in the settings
        then the fuel name should be <region>_<fuel>.
    model_year : int, optional
        Model year for fuel costs. Used as fallback if no settings context is available.
    fuel_emission_factors : dict, optional
        CO2 emissions in tonnes per MMBTU for each fuel type used. Used as fallback if no
        settings context is available.
    fuel_scenarios : dict, optional
        Fuel scenario definitions. Used as fallback if no settings context is available.
    user_fuel_price : dict, optional
        User-defined fuel prices. Used as fallback if no settings context is available.
        Prices can either be a single price for all regions or a price per region. For 
        example this shows biomass with different prices in two regions and ZCF with 
        the same price in all regions:

        settings["user_fuel_price"] = {
            "biomass": {"SC_VACA": 10, "PJM_DOM": 5},
            "ZCF": 15
        }
        
        If the keys "target_usd_year" and "user_fuel_usd_year" are also included, fuel
        prices will be corrected to the correct USD year. "user_fuel_usd_year" should
        be a dictionary with fuel name: USD year pairings. Only fuels included in this
        dictionary will have their prices changed to the target USD year.
    ccs_fuel_map : dict, optional
        Mapping of CCS fuel names. Used as fallback if no settings context is available.
    co2_pipeline_filters : bool, optional
        Whether to apply CO2 pipeline filters. Used as fallback if no settings context is available.
    co2_pipeline_cost_fn : str, optional
        CO2 pipeline cost function name. Used as fallback if no settings context is available.
    ccs_disposal_cost : float, optional
        CCS disposal cost. Used as fallback if no settings context is available.
    ccs_capture_rate : dict, optional
        CCS capture rates. Used as fallback if no settings context is available.
    carbon_tax : float, optional
        Carbon tax value. Used as fallback if no settings context is available.
    reduce_time_domain : bool, optional
        Whether to reduce time domain. Used as fallback if no settings context is available.
    time_domain_days_per_period : int, optional
        Days per period for time domain reduction. Used as fallback if no settings context is available.
    time_domain_periods : int, optional
        Number of periods for time domain reduction. Used as fallback if no settings context is available.
    num_hours : int, optional
        Number of hours in the model. Used as fallback if no settings context is available.
    target_usd_year : int, optional
        Target year for USD values. Used as fallback if no settings context is available.
    user_fuel_usd_year : dict, optional
        USD year for user-defined fuel prices. Used as fallback if no settings context is available.
    data_location : Path, optional
        Path to the data location. Used as fallback if no settings context is available.
    dollar_year_table : str, optional
        Name of the table in the data location that contains dollar year conversions. Used as fallback if no settings context is available.

    Returns
    -------
    pd.DataFrame
        The cost of fuels used by generators in the final year of a modeling period.
        Formatted for GenX, where headers are the fuel names, the first row is the
        fuel CO2 content (tonnes per MMBTU), and subsequent rows are hourly prices.
        Prices are identical in all hours. The first (index) column has the header
        "Time_Index" and values from 0-N, where N is the number of hours used in the model.
    """
    # First try to get settings from context manager
    try:
        settings = get_current_settings()
        logger.debug("Using settings from context manager")
        model_year = settings["model_year"]
        fuel_emission_factors = settings.get("fuel_emission_factors")
        fuel_scenarios = settings.get("fuel_scenarios")
        user_fuel_price = settings.get("user_fuel_price")
        ccs_fuel_map = settings.get("ccs_fuel_map")
        co2_pipeline_filters = settings.get("co2_pipeline_filters")
        co2_pipeline_cost_fn = settings.get("co2_pipeline_cost_fn")
        ccs_disposal_cost = settings.get("ccs_disposal_cost")
        ccs_capture_rate = settings.get("ccs_capture_rate")
        carbon_tax = settings.get("carbon_tax")
        reduce_time_domain = settings.get("reduce_time_domain")
        time_domain_days_per_period = settings["time_domain_days_per_period"]
        time_domain_periods = settings["time_domain_periods"]
        target_usd_year = settings.get("target_usd_year")
        user_fuel_usd_year = settings.get("user_fuel_usd_year")
        data_location = settings.get("data_location")
        dollar_year_table = settings.get("dollar_year_table")
    except NoSettingsError:
        logger.debug("No settings context available, using explicit parameters")

    all_fuel_costs = add_user_fuel_prices(
        fuel_costs,
        user_fuel_price,
        target_usd_year=target_usd_year,
        user_fuel_usd_year=user_fuel_usd_year,
        data_location=data_location,
        dollar_year_table=dollar_year_table,
    )
    unique_fuels = generators["Fuel"].drop_duplicates()
    model_year_costs = all_fuel_costs.loc[
        all_fuel_costs["year"] == model_year, :
    ]
    fuel_df = pd.DataFrame(unique_fuels)

    fuel_price_map = {
        row.full_fuel_name: row.price
        for row in model_year_costs.itertuples(index=False, name="row")
    }

    emission_dict = fuel_emission_factors or {}
    user_fuels = set(all_fuel_costs["fuel"]) - set(fuel_costs["fuel"])
    for u_f in user_fuels:
        if u_f not in emission_dict.keys():
            logger.warning(
                "\n\n**********************\n"
                f"The user fuel {u_f} does not have an emissions factor specified in "
                "the settings parameter 'fuel_emission_factors'. This is fine if the "
                "emission factor should be 0, otherwise be sure to add a value.\n"
            )
    fuel_emission_map = {}
    for full_fuel_name in fuel_price_map:
        if (
            full_fuel_name.split("_")[-1]
            in (fuel_scenarios or {}).keys()
        ):
            base_fuel_name = full_fuel_name.split("_")[-1]
        elif (
            full_fuel_name.split("_")[-1]
            in (user_fuel_price or {}).keys()
        ):
            base_fuel_name = full_fuel_name.split("_")[-1]
        else:
            base_fuel_name = full_fuel_name
        if base_fuel_name in emission_dict:
            fuel_emission_map[full_fuel_name] = emission_dict[base_fuel_name]
        else:
            fuel_emission_map[full_fuel_name] = 0

    ccs_fuels = (ccs_fuel_map or {}).values()
    for ccs_fuel in ccs_fuels:
        fuels = generators.loc[
            generators["Fuel"].str.contains(ccs_fuel), "Fuel"
        ].unique()
        for f in fuels:
            # keep the non-ccs price
            base_name = ("_").join(f.split("_")[:-1])
            fuel_price_map[f] = fuel_price_map[base_name]
            fuel_emission_map[f] = fuel_emission_map[base_name]

    fuel_df["Cost_per_MMBtu"] = fuel_df["Fuel"].map(fuel_price_map)
    fuel_df["CO2_content_tons_per_MMBtu"] = fuel_df["Fuel"].map(fuel_emission_map)

    # Slow to loop through all of the rows this way but the df shouldn't be too long
    if co2_pipeline_filters and co2_pipeline_cost_fn:
        ccs_disposal_cost = 0
    else:
        ccs_disposal_cost = ccs_disposal_cost or 0
    fuel_df = fuel_df.apply(
        adjust_ccs_fuels,
        axis=1,
        ccs_fuels=(ccs_fuel_map or {}).values(),
        ccs_capture_rate=(ccs_capture_rate or {}),
        ccs_disposal_cost=ccs_disposal_cost,
    )
    fuel_df = add_carbon_tax(fuel_df, carbon_tax)
    fuel_df["Cost_per_MMBtu"] = fuel_df["Cost_per_MMBtu"]
    fuel_df["CO2_content_tons_per_MMBtu"] = fuel_df["CO2_content_tons_per_MMBtu"]
    fuel_df.fillna(0, inplace=True)

    if reduce_time_domain:
        days = time_domain_days_per_period
        time_periods = time_domain_periods
        num_hours = days * time_periods * 24
    elif num_hours is None:
        num_hours = 8760

    fuel_df_prices = pd.DataFrame(
        [fuel_df["Cost_per_MMBtu"]], index=range(1, num_hours + 1)
    )
    fuel_df_prices = fuel_df_prices.round(2)
    fuel_df_prices.columns = unique_fuels

    fuel_df_top = pd.DataFrame([fuel_df["CO2_content_tons_per_MMBtu"]])
    fuel_df_top = fuel_df_top.round(5)
    fuel_df_top.columns = unique_fuels
    fuel_df_top.index = [0]

    fuel_frames = [fuel_df_top, fuel_df_prices]
    fuel_df_new = pd.concat(fuel_frames)
    fuel_df_new.index.name = "Time_Index"
    return fuel_df_new


# def modify_fuel_new_genx():


def adjust_ccs_fuels(
    ccs_fuel_row: pd.Series,
    ccs_fuels: List[str] = None,
    ccs_capture_rate: Dict[str, float] = {},
    ccs_disposal_cost: float = None,
) -> pd.Series:
    """Adjust the "CO2_content_tons_per_MMBtu" and "Cost_per_MMBtu" values to account for
    the value from settings parameter "ccs_capture_rate".

    If using this function to adjust the CO2 content and cost for CCS-specific fuels,
    the settings dict should map the names of technologies to a base CCS fuel name in the
    parameter "ccs_fuel_map". The base CCS fuel names do not include a region or scenario,
    they are something like "naturalgas_ccs90".


    Parameters
    ----------
    ccs_fuel_row : pd.Series
        A single row from the larger fuel dataframe with columns "Fuel", "Cost_per_MMBtu",
        and "CO2_content_tons_per_MMBtu".
    ccs_fuels : List[str], optional
        A list of CCS fuels mapped to generator types, by default None
    ccs_capture_rate : Dict[str, float], optional
        The capture rate (0-1) for each CCS fuel type in `ccs_fuels`, by default {}
    ccs_disposal_cost : float, optional
        The cost in USD per tonne of CO2 disposal that should be added to a fuel price,
        by default None

    Returns
    -------
    pd.Series
        If the fuel is mapped to a CCS technology, the "CO2_content_tons_per_MMBtu" and
        "Cost_per_MMBtu" values will be modified.

    Raises
    ------
    KeyError
        One of the CCS fuels mapped to a technology is not included in the "ccs_capture_rate"
        dict.
    """

    base_fuel_name = None
    for ccs_fuel in ccs_fuels or []:
        if ccs_fuel not in ccs_capture_rate.keys():
            raise KeyError(
                f"The CCS fuel name {ccs_fuel} from settings parameter 'ccs_fuel_map' "
                "does not have capture rate in the settings parameter 'ccs_capture_rate'."
                "Adjust your settings to include the capture rate or remove the fuel."
            )
        if ccs_fuel in ccs_fuel_row["Fuel"]:
            base_fuel_name = ccs_fuel
    if base_fuel_name:
        # USD/tonne disposal
        if not ccs_disposal_cost:
            logger.debug(
                "You did not specify a fuel-modifying CCS disposal cost, so it will be set to $0. "
                "Set a non-zero value with the settings parameter 'ccs_disposal_cost'."
            )
            ccs_disposal_cost = 0

        capture_rate = ccs_capture_rate.get(base_fuel_name, 0)

        co2_captured = ccs_fuel_row["CO2_content_tons_per_MMBtu"] * capture_rate

        ccs_fuel_row["CO2_content_tons_per_MMBtu"] -= co2_captured
        ccs_fuel_row["Cost_per_MMBtu"] += co2_captured * ccs_disposal_cost

    else:
        pass

    return ccs_fuel_row


def add_carbon_tax(
    fuel_df: pd.DataFrame, carbon_tax_value: float = None
) -> pd.DataFrame:
    """Increases fuel prices to account for a carbon tax

    Parameters
    ----------
    fuel_df : pd.DataFrame
        Table with columns "Cost_per_MMBtu" and "CO2_content_tons_per_MMBtu"
    carbon_tax_value : float, optional
        The carbon tax cost in USD per tonne CO2, by default None.

    Returns
    -------
    pd.DataFrame
        Modified version of input df with fuel prices increased to reflect the carbon tax.
        The df is returned unaltered if no carbon tax is provided.
    """
    if not carbon_tax_value:
        return fuel_df

    for col in ["Cost_per_MMBtu", "CO2_content_tons_per_MMBtu"]:
        if col not in fuel_df.columns:
            raise KeyError(
                f"The required column {col} is missing from your fuel dataframe. Cannot "
                "apply a carbon tax to fuel prices without this column."
            )

    fuel_df.loc[:, "Cost_per_MMBtu"] = fuel_df.loc[:, "Cost_per_MMBtu"] + (
        fuel_df.loc[:, "CO2_content_tons_per_MMBtu"] * carbon_tax_value
    )

    return fuel_df
