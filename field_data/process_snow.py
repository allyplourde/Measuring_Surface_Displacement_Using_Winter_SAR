"""
File: process_snow.py
Author: Allison Plourde
Date: September 20, 2023
Description: This script processes the snow depth data collected from Judd Snow Depth Sensors
"""

# external packages
import pandas as pd
import numpy as np
import re
import os  
import glob
import matplotlib.pyplot as plt

# internal packages
from process_tilt import getMetData

#Snow Logger Data Directory
field_dir = '/local-scratch/users/aplourde/field_data/'
files = glob.glob(field_dir + '/*/*snow_depth.csv')

# Analysis Period
start_date = pd.to_datetime('2019-06-01') # date of initial installation
#start_date = pd.to_datetime('2022-07-21')
end_date = pd.to_datetime('2023-08-01') # date of last retrieval

# Plotting Parameters
n_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
xtics = pd.date_range(start=start_date, end=end_date, freq='M').tolist()

# Snow on Ground Dates based on Environment Canada Data at Inuvik climate station
snow_on_ground = {'2019': [pd.to_datetime('2019-10-05'), pd.to_datetime('2020-05-23')],
                  '2020': [pd.to_datetime('2020-10-09'), pd.to_datetime('2021-05-14')],
                  '2021': [pd.to_datetime('2021-09-27'), pd.to_datetime('2022-05-10')],
                  '2022': [pd.to_datetime('2022-09-27'), pd.to_datetime('2023-06-01')]}


def importData(file):
    """
    This function imports the raw data from the csv file.
    :param file: the csv file containing the raw data

    :return: a pandas dataframe containing the raw data
    """

    # import data
    df = pd.read_csv(file)
    cols = list(df) # get column names

    # convert date to datetime object
    date = pd.to_datetime(df[cols[0]].values, utc=True).tz_localize(None)

    # ensure consistent data types
    out = pd.DataFrame(data = {'date': date, 'snow_depth': np.float64(df[cols[1]])})

    return out


def processData(file):
    """
    This function processes the raw data from the csv file.
    :param file: the csv file containing the raw data

    :return: a pandas dataframe containing the processed data
    """

    # import data
    data = importData(file)

    # initialize output dataframe
    out = pd.DataFrame(index = data.date)

    # retrieve logger snow depth
    out['snow_depth_cm'] = data['snow_depth'].values * 2.54 # convert inches to cm

    # ensure data is in order
    out = out.sort_index()

    # truncate data to start/end date
    out = out.loc[out.index >= start_date]
    out = out.loc[out.index <= end_date]

    return out


def combine_snow_with_EC(sdf, site):
    """
    This function combines the snow depth data with Environment Canada data
    from the Inuvik and Trail Valley climate stations.
    :param sdf: the snow depth dataframe
    :param site: the site name

    :return: the snow depth dataframe with Environment Canada data
    """

    inuvik_met_dir = '../met_data/env_canada/Inuvik/'
    trailvalley_met_dir = '../met_data/env_canada/TrailValley/'

    # get Environment Canada data
    sdf = getMetData(sdf, met_dir=inuvik_met_dir)
    sdf = getMetData(sdf, met_dir=trailvalley_met_dir)

    # set snow depth to nan if no snow on ground at Inuvik
    sdf.loc[sdf['Snow on Grnd (cm)_x'].isna(), 'snow_depth_cm'] = np.nan    

    return sdf


def combine_snow_with_ERA5(sdf, site):
    """
    This function combines the snow depth data with ERA5 Re-Analysis data
    from the Inuvik and Trail Valley climate stations.
    :param sdf: the snow depth dataframe
    :param site: the site name

    :return: the snow depth dataframe with Environment Canada data
    """

    era5_dir = '/local-scratch/users/aplourde/met_data/era5/delta_snow_depth/'

    # get Environment Canada data
    sdf = getMetData(sdf, met_dir=inuvik_met_dir)
    sdf = getMetData(sdf, met_dir=trailvalley_met_dir)

    # set snow depth to nan if no snow on ground at Inuvik
    sdf.loc[sdf['Snow on Grnd (cm)_x'].isna(), 'snow_depth_cm'] = np.nan

    return sdf


def correct_for_heave(sdf, site):
    """
    This function corrects the snow depth data for heave as recorded 
    by the inclinometer data at each site.
    :param sdf: the snow depth dataframe
    :param site: the site name

    :return: the snow depth dataframe with heave corrected
    """

    sdf_copy = sdf.copy() # make copy of dataframe to store corrected snow depth
    sdf.snow_depth_cm = np.nan # set snow depth to nan

    # get inclinometer file for the corresponding site
    tilt_file = glob.glob(f"*/{site}/{site}_inclinometer_processed.csv")[0] 
    tdf = pd.read_csv(tilt_file, index_col=0) # import tilt data
    tdf.index = pd.to_datetime(tdf.index) # convert index to datetime

    sdf_copy['dh1_mm'] = np.nan # initialize column for heave

    for index, row in sdf.iterrows(): # iterate through snow depth dataframe
        if index in tdf.index.values: # if there is a tilt measurement for the given date
            sdf_copy.dh1_mm.loc[index] = tdf.dh1_mm.loc[index] # store heave measurement

    sdf['snow_sub_heave'] = np.nan # initialize column for corrected snow depth
    for year in snow_on_ground: # iterate through years

        # truncate data to season
        season = sdf_copy[sdf_copy.index >= snow_on_ground[year][0]] 
        season = season[season.index < snow_on_ground[year][1]] 

        if site == 'site_2' and year == '2019': # site 2 failed in 2020
            season = season[season.index < pd.to_datetime('2020-04-12')]

        try: # try to zero snow depth at beginning of season
            corrected_sd = season.snow_depth_cm - season.snow_depth_cm.loc[snow_on_ground[year][0]]
            corrected_dh = season.dh1_mm - season.dh1_mm.loc[snow_on_ground[year][0]]
        except: # skip the correction if there is no data at the beginning of the season
            corrected_sd = season.snow_depth_cm
            corrected_dh = season.dh1_mm

        dh_copy = corrected_dh # make copy of heave measurements
        dh_copy = dh_copy*0.1 # convert mm to cm
        dh_copy[np.isnan(dh_copy)] = 0 # set nan values to zero

        # correct snow depth for heave
        sdf['snow_depth_cm'].loc[corrected_sd.index] = corrected_sd # store uncorrected data
        sdf['snow_sub_heave'].loc[corrected_sd.index] = corrected_sd - dh_copy # subtract heave from snow depth
        sdf['heave_cm'] = corrected_dh*0.1 # store heave measurements in cm
        sdf.loc[sdf.snow_depth_cm < 0] = np.nan # set negative snow depths to nan

    return sdf


def plotAll(snow_depth):
    """
    This function plots the snow depth data for all sites.
    :param snow_depth: a dictionary containing the snow depth dataframes for each site

    :return: None
    """

    # plotting parameters for each site
    style_map = {'site_1': {'color': '#e41a1c', 'linestyle': '-', 'label': "Site 1: Homogenous 1"},
                 'site_2': {'color': '#377eb8', 'linestyle': '-', 'label': "Site 2: Low Ground"},
                 'site_3': {'color': '#4daf4a', 'linestyle': '--', 'label': "Site 3: High Ground"},
                 'site_4': {'color': '#ff7f00', 'linestyle': '--', 'label': "Site 4: Homogenous 2"},
                 'site_5': {'color': '#984ea3', 'linestyle': '-.', 'label': "Site 5: Hill Top"},
                 'site_6': {'color': '#a65628', 'linestyle': '-.', 'label': "Site 6: Jimmy Lake"}
                 }

    # create figure with single snow-depth plot
    fig, axes = plt.subplots(1, 1, sharex='col', sharey=False, gridspec_kw={'wspace': 0, 'hspace': 0})

    # plot snow depth for each site
    for site, df in snow_depth.items():

        if site == 'site_4': # skip site 4
            continue

        # plot snow depth
        if site == 'site_2': # plot snow depth without heave correction for site 2
            axes.plot(df.index, df['snow_depth_cm'], style_map[site]['linestyle'], color=style_map[site]['color'], label=style_map[site]['label'])
        else: # plot snow depth with heave correction for all other sites
            axes.plot(df.index, df['snow_sub_heave'], style_map[site]['linestyle'], color=style_map[site]['color'],
                 label=style_map[site]['label'])

    # plot snow at Inuvik and Trail Valley
    axes.plot(snow_depth['site_1'].index, snow_depth['site_1']['Snow on Grnd (cm)_x'], color='black', label='Inuvik')
    axes.plot(snow_depth['site_1'].index, snow_depth['site_1']['Snow on Grnd (cm)_y'], '--', color='black', label='TrailValley')

    axes.legend() # add legend
    axes.set_ylabel("Snow Depth (cm)") # add y-axis label

    # only label every other month
    class XFormatter:
        def __call__(self, x, pos=None):
            return '' if pos % 2 else f'{x:.1f}'

    xlabels = []
    for i, label in enumerate(xtics):
        # For every third month, format the label as 20XX-XX
        xlabels.append('') if i % 3 else xlabels.append(label.strftime('%Y-%m'))

    axes.set_xlabel("Date") # add x-axis label
    axes.set_xticks(xtics) # set x-ticks
    axes.set_xticklabels(xlabels) # set x-tick labels
    axes.set_xlim(start_date, end_date) # set x-axis limits

    plt.show()

    return


if __name__ == "__main__":

    # import raw data
    snow_depth = {}
    for file in files:
        # get site name
        site = re.search(r'site_.', file).group(0)

        # process data
        data = processData(file)

        # resample to daily
        sdf = data.resample('D').mean()

        # correct for heave
        snow_depth[site] = correct_for_heave(sdf, site)
        
        # combine with Environment Canada data
        snow_depth[site] = combine_snow_with_EC(snow_depth[site], site)
        snow_depth[site] = combine_snow_with_ERA5(snow_depth[site], site)

        # save processed data
        outdir = os.path.join(field_dir, site) 
        outfile = os.path.join(outdir, site + '_snow_depth_processed.csv')
        snow_depth[site].to_csv(outfile)

    plotAll(snow_depth)