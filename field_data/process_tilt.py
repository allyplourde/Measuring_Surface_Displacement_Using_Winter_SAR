"""
File: process_tilt.py
Author: Allison Plourde
Date: September 20, 2023
Description: This script reads inclinometer data from both RST and GeoPrecision tilt loggers. The data
             is processed to calculate the vertical deflection of the ground surface. Processing steps
             are based on Gruber (2020), all other code is original.
"""

# external packages
import pandas as pd
import numpy as np
import os
import glob
import re
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

# internal packages
from sarlab.met import parse_ec_dir

# Directories
MET_DIR = '/local-scratch/users/aplourde/met_data/env_canada/Inuvik/'   #Environment Canada Meteorological Data Directory
DATA_DIR = '/local-scratch/users/aplourde/field_data/'  #Tilt Logger Data Directory
files = glob.glob(DATA_DIR + '/*/*inclinometer.csv')

# Analysis Period
start_date = pd.to_datetime('2018-08-27')   # Date of first inclinometer installation
#start_date = pd.to_datetime('2022-07-21')
end_date = pd.to_datetime('2023-08-01')

# Plotting Parameters
n_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
xtics = pd.date_range(start=start_date, end=end_date, freq='M').tolist()
dlim = [-95, 55]  # y-axis limits for vertical deformation
clim = [0, 30]  # y-axis limits for percipitation

# Inclinometer Parameters
arm_length = {'site_1': 1470,   # length of inclinometer arm in mm
              'site_2': 1490,
              'site_3': 1520,
              'site_4': 1575,
              'site_5': 1590,
              'site_6': 1750}
pivot_height = {'site_1': 120,  # height of inclinometer pivot in mm
                'site_2': 140,
                'site_3': 140,
                'site_4': 385,
                'site_5': 495,
                'site_6': 360}

# Meterological Dates
first_freeze_date = pd.to_datetime(['20180913',
                                    '20191006',
                                    '20200912',
                                    '20210924',
                                    '20220927'])
sustained_freeze_date = pd.to_datetime(['20181002',
                                        '20191031',
                                        '20201010',
                                        '20211007',
                                        '20221010'])

first_thaw_date = pd.to_datetime(['20190317',
                                  '20200508',
                                  '20210414',
                                  '20220424',
                                  '20230501'])
sustained_thaw_date = pd.to_datetime(['20190510',
                                      '20200520',
                                      '20210602',
                                      '20220524',
                                      '20230529'])


def importData(file):
    """
    Imports data from tilt logger csv file
    :param file: path to csv file

    :return: pandas dataframe
    """

    df = pd.read_csv(file) # import data
    cols = list(df) # get column names

    # ensure consistent data types and place into a dataframe
    out = pd.DataFrame(index = pd.to_datetime(df[cols[0]]),
                      data = {'angle_1': np.float64(df[cols[1]]),
                              'angle_2': np.float64(df[cols[2]]),
                              'logger_temp_c': np.float64(df[cols[3]])})

    return out


def convertAngles(angle_rads, site, flip = False):
    """
    Converts tilt logger angles to vertical deflection; adapted from Gruber (2020).
    :param angle_rads: tilt logger angle in rads
    :param site: site name
    :param flip: boolean, whether or not to flip the sign of the vertical deflection
                 (useful for inclinometers that are installed backwards)

    :return: vertical deflection in mm
    """

    # vertical distance of arm end from horizontal
    dYL = np.sin(angle_rads) * arm_length[site] # could use small angle approximation sinx = x
    if flip: 
        dYL = -1 * dYL # flip sign of vertical deflection

    # horizontal distance of actual arm end from horizontal arm end
    dX = (1 - np.cos(angle_rads)) * arm_length[site]

    # vertical distance added by double pivot
    dYP = np.sqrt(pivot_height[site]**2 - dX**2)

    # total vertical displacement
    dY = dYL + dYP

    return dY


def processData(file):
    """
    Processes tilt logger data to calculate vertical deflection
    :param file: path to csv file

    :return: pandas dataframe
    """
    
    data = importData(file)     # import data
    site = file.split('/')[-2]  # get site name

    out = pd.DataFrame(index=data.index) # create output dataframe

    # retrieve logger temp
    out['logger_temp_c'] = data['logger_temp_c'] # logger temp in degrees Celsius

    # calculate deflection
    out['h1_mm'] = convertAngles(data['angle_1'], site)  # vertical deflection in mm
    #out['h2_mm'] = convertAngles(data['angle_2'])

    out[out.isna()] = 0     # replace NaNs with zeros
    out = out.sort_index()  # sort by date

    # truncate data to start/end date
    out = out.loc[out.index >= start_date]
    out = out.loc[out.index <= end_date]

    # throwaway errouneous data (sensor may malfuction below -40C)
    out.h1_mm.loc[out.logger_temp_c < -35] = np.nan

    # calculate relative deflection in mm
    out['dh1_mm'] = out['h1_mm'] - out['h1_mm'].loc[~out['h1_mm'].isnull()].iloc[0] 
    #out['dh2_mm'] = out['h2_mm'] - out['h2_mm'].loc[~out['h2_mm'].isnull()].iloc[0]

    return out


def errorDueToTermalExpansion():
    pass

def getMetData(df, met_dir=MET_DIR):
    """
    Gets meteorological data from Environment Canada
    :param df: pandas dataframe
    :param met_dir: path to meteorological data directory

    :return: pandas dataframe
    """
    # import meteorological data into a dictionary
    # expected keys:
    # ['Longitude (x)', 'Latitude (y)', 'Station Name', 'Climate ID', 'Date/Time', 'Data Quality', 'Max Temp (°C)', 
    # 'Min Temp (°C)', 'Mean Temp (°C)', 'Heat Deg Days (°C)', 'Cool Deg Days (°C)', 'Total Rain (mm)', 'Total Snow (cm)', 
    # 'Total Precip (mm)', 'Snow on Grnd (cm)', 'Dir of Max Gust (10s deg)', 'Spd of Max Gust (km/h)', 'Elevation']
    met_dict = parse_ec_dir(met_dir, freq='daily', plot=False) 

    met_df = pd.DataFrame(data=met_dict)    # create dataframe
    met_df.index = pd.to_datetime(met_df['Date/Time'])  # set index to date

    # merge tilt logger and meteorological data on date index
    out_df = df.merge(met_df, how='left', left_index=True, right_index=True)    

    return out_df

def shade_freeze_thaw(ax):
    """
    Plotting utility for shading the freeze/thaw periods
    :param ax: matplotlib axis object

    :return: None
    """
    
    for i in range(len(first_freeze_date)): # for each year
        ax.axvspan(first_freeze_date[i], sustained_freeze_date[i], color='lightcoral', alpha=.25)   # transition
        ax.axvspan(sustained_freeze_date[i], first_thaw_date[i], color='deepskyblue', alpha=.25)    # sustained freeze
        ax.axvspan(first_thaw_date[i], sustained_thaw_date[i], color='skyblue', alpha=.25) # transition

        if i < len(first_freeze_date)-1:    # if not the last year
            ax.axvspan(sustained_thaw_date[i], first_freeze_date[i + 1], color='coral', alpha=.25)  # sustained thaw
        else: # if last year shade till end date (assuming end date is in summer)
            ax.axvspan(sustained_thaw_date[i], end_date, color='coral', alpha=.25)  # sustained thaw

    return


def plotAll(vertical_deformation):
    """
    Plots vertical deformation, temperature, and precipitation for all sites
    :param vertical_deformation: dictionary of pandas dataframes

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

    # create figure with 2 subplots (top: vertical deformation, bottom: temperature and precipitation)
    fig, axes = plt.subplots(2, 1, sharex='col', sharey=False, gridspec_kw={'wspace': 0, 'hspace': 0})
    # fig, axes = plt.subplots(3, 1, sharex='col', sharey=False, gridspec_kw={'wspace': 0, 'hspace': 0})

    fig.suptitle("Vertical Deflection\n")

    # shade the freeze/thaw periods
    shade_freeze_thaw(axes[0])
    shade_freeze_thaw(axes[1])

    # plot vertical deformation for each site
    for site in vertical_deformation:
        # truncate data to start date
        vertical_deformation[site] = vertical_deformation[site][vertical_deformation[site].index 
                                                                >= pd.to_datetime(start_date)]

        axes[0].plot(vertical_deformation[site].index,
                 vertical_deformation[site]['dh1_mm'] - vertical_deformation[site]['dh1_mm'].iloc[0],
                 style_map[site]['linestyle'], color=style_map[site]['color'], label=style_map[site]['label'])

    axes[0].set_ylabel('Vertical Deformation (mm)') # set y-axis label
    axes[0].set_ylim(dlim) # set y-axis limits

    # plot temperature and precipitation at EC station
    twnx = axes[1].twinx() # create second y-axis

    # plot temperature on right y-axis
    t, = twnx.plot(vertical_deformation['site_1'].index, vertical_deformation['site_1']['Mean Temp (°C)'], color='grey',
                   label='Mean Daily Temperature')
    # plot 0°C line
    twnx.plot([vertical_deformation['site_1'].index[0], vertical_deformation['site_1'].index[-1]], [0, 0], '--',
              color='grey')
    
    # plot precipitation on left y-axis
    p, = axes[1].plot(vertical_deformation['site_1'].index, vertical_deformation['site_1']['Total Precip (mm)'],
                      color='black', label='Total Daily Precipitation')

    axes[1].set_ylabel('Percipitation (mm)') # set y-axis left label
    twnx.set_ylabel('Temperatures (°C)') # set y-axis right label
    axes[1].set_ylim(clim) # set y-axis left limits

    # set x-axis limits
    class XFormatter:
        def __call__(self, x, pos=None):
            return '' if pos % 2 else f'{x:.1f}' # only label every other month

    xlabels = []
    for i, label in enumerate(xtics): 
        # For every third month, format the label as 20XX-XX
        xlabels.append('') if i % 3 else xlabels.append(label.strftime('%Y-%m'))

    axes[1].set_xlabel("Date") # set x-axis label
    axes[1].set_xticks(xtics) # set x-axis ticks
    axes[1].set_xticklabels(xlabels) # set x-axis tick labels
    axes[1].set_xlim(start_date, end_date) # set x-axis limits

    axes[0].legend() # add legend to vertical deformation plot
    axes[1].legend(handles=[t, p]) # add legend to temperature and precipitation plot

    plt.show() # show plot

    return


def plotIndividual(vertical_deformation, site):
    """
    Plots vertical deformation, temperature, and precipitation for a single site
    :param vertical_deformation: pandas dataframe
    :param site: site name (eg 'site_1', expected as key in vertical deformation dictionary)

    :return: None
    """
    # Create a new dictionary with only the desired keys
    subset_dict = {site: vertical_deformation[site]}

    global dlim     # adjust the global variable dlim
    dlim = [None, None]   # remove limits for y-axis plot

    # Plot the data for the desired site
    plotAll(subset_dict)

    return


if __name__ == "__main__":

    # initialize dictionary to store processed data
    vertical_deformation = {}

    for file in files:
        site = re.search(r'site_.', file).group(0) # get site name
        print(file)
        data = processData(file) # process data

        # add processed data to dictionary, resampling to daily median
        vertical_deformation[site] = data.resample('D').median()
        # concatenate inclinometer with meterological data
        vertical_deformation[site] = getMetData(vertical_deformation[site])

    # save processed data to csv for each site
    for site, df in vertical_deformation.items():
        outdir = os.path.join(DATA_DIR, site) # create output directory
        outfile = os.path.join(outdir, site + '_inclinometer_processed.csv') # create output file path
        df.to_csv(outfile) # save data to csv

    # plot all sites
    plotAll(vertical_deformation) 

    # plot individual sites
    site_to_plot = 'site_1' # 'site_1', 'site_2', 'site_3', 'site_4', 'site_5', 'site_6
    plotIndividual(vertical_deformation, site_to_plot)










