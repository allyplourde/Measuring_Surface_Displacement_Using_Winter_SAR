"""
File: merge_datasets.py
Author: Allison Plourde
Date: September 20, 2023
Description: This script merges the tilt and sonar data from each site into a single csv file.
"""

# external packages
import numpy as np
import pandas as pd
import os
import glob
import matplotlib.pyplot as plt

# Global Variables
SHOW_PLOTS = False
MAX_SNOW_VAL = 100

# logger names
TILTS = {'site_1/': "05119",
         'site_2/': "05123",
         'site_3/': "A543E3",
         'site_4/': "A543D4",
         'site_5/': "A543D1",
         'site_6/': "A543D3"}


def process_all(site):
    """
    This function finds all the tilt and sonar data files for a given site and calls
    the concat_sonar and concat_tilt functions.
    :param site: the site directory

    :return: None
    """

    sonar = []
    tilt = []

    datasets = glob.glob(os.path.join(site, '*/')) # get all site directories

    # loop through site directories
    for site_dir in datasets:
        data = glob.glob(site_dir + '*') # get all files in site directory
        for file in data:
            if 'hobo' in file and 'csv' in file: # judd snow depth files
                sonar.append(file)
            elif 'maxsonar' in file and 'csv' in file: # maxsonar (obsolete)
                sonar.append(file)
            elif TILTS[site] in file and 'cleaned' in file: # cleaned tiltlogger files
                tilt.append(file)

    if len(sonar) > 0:
        concat_sonar(sonar, site) # merge sonar data
    if len(tilt) > 0:
        concat_tilt(tilt, site) # merge tilt data

    return
    

def concat_sonar(files, out_dir):
    """
    This function concatenates the sonar data from each file into a single csv file.
    :param files: list of sonar data files
    :param out_dir: the output directory

    :return: None
    """

    df = pd.DataFrame() # initialize dataframe

    for file in files:
        df_new = pd.read_csv(file, skiprows=1) # read in data

        date_col = list(df_new)[1] # get date column
        snow_col = list(df_new)[2] # get snow depth column

        if 'site_4' in file:
            df_new[snow_col] = 0 # ignore site 4

        #ignore errouneous data
        df_new = df_new.where(df_new[snow_col] < MAX_SNOW_VAL)
        df_new = df_new.where(df_new[snow_col] > -MAX_SNOW_VAL)

        # check units
        if 'inches' in snow_col: 
            unit = 'in'
        else:
            print("Snow depth should be inches (check units) !!!!!")
            unit = 'in'
            #return

        timezone = date_col.split('GMT')[1] # get timezone
        df_new[date_col] = df_new[date_col] + timezone # add timezone to date column

        datetimes = pd.to_datetime(df_new[date_col]) # convert to datetime
        snowdepth = df_new[snow_col].values # get snow depth values

        # create new dataframe to concatenate with existing dataframe
        concat = pd.DataFrame(index=datetimes, data={'snow_depth_'+unit: snowdepth}) 

        df = pd.concat([df, concat]) # concatenate dataframes
        df = df[~df.index.duplicated(keep='first')] # remove duplicate rows

        if SHOW_PLOTS:
            df.plot()
            plt.show()

    # save dataframe to csv
    out = os.path.join(out_dir, out_dir[:-1]+'_snow_depth.csv')
    df.to_csv(out)

    return
    

def concat_tilt(files, out_dir):
    """
    This function concatenates the tilt data from each file into a single csv file.
    :param files: list of tilt data files
    :param out_dir: the output directory

    :return: None
    """
    
    df = pd.DataFrame() # initialize dataframe

    for file in files:
        if "A54" in file: # site 3, 4, 5, 6 GeoPrecision tilt logger
            skip = 9
        else: # site 1, 2 RST tilt logger
            skip = 14
        
        # read in data
        df_new = pd.read_csv(file, skiprows=skip)

        if "A54" in file: #site 3, 4, 5, 6

            df_new = df_new[:-1]  # drop last row
            date_col = list(df_new)[1] # get date column

            tilt_col1 = list(df_new)[4] # get first tilt column
            tilt_col2 = list(df_new)[3] # get second tilt column
            temp_col = list(df_new)[2] # get logger temperature column

            # ignore erroneous data
            df_new = df_new[df_new[tilt_col1] != '(Err_64)'] 
            df_new = df_new[df_new[tilt_col1] != '(NoValue)']

            # convert to datetime
            datetimes = pd.to_datetime(df_new[date_col], format='%d.%m.%Y %H:%M:%S').values 

            # create new dataframe to concatenate with existing dataframe
            concat = pd.DataFrame(index=datetimes, 
                                data={'angle_1': np.deg2rad(np.float32(df_new[tilt_col1].values)),
                                      'angle_2': np.deg2rad(np.float32(df_new[tilt_col2].values)),
                                      'logger_temp_c': df_new[temp_col].values}
            )  

        else:

            date_col = list(df_new)[0] # get date column

            # convert to datetime
            datetimes = pd.to_datetime(df_new[date_col]).values

            if '1' in out_dir: # site 1, keep tilt order as is
                tilt_col1 = list(df_new)[3]
                tilt_col2 = list(df_new)[4]
            elif '2' in out_dir: # site 2, switch tilt order
                tilt_col1 = list(df_new)[4]
                tilt_col2 = list(df_new)[3]
            else:
                # ignore site 3
                concat = pd.DataFrame(index=[],
                                      data={'angle_1': [],
                                            'angle_2': [],
                                            'logger_temp_c': []}
                                      )

            temp_col = list(df_new)[10] # get logger temperature column

            # create new dataframe to concatenate with existing dataframe
            concat = pd.DataFrame(index=datetimes, 
                                data={'angle_1': df_new[tilt_col1].values,
                                      'angle_2': df_new[tilt_col2].values,
                                      'logger_temp_c': df_new[temp_col].values}
            )

        df = pd.concat([df, concat]) # concatenate dataframes
        df = df.sort_index() # sort by datetime
        df = df[~df.index.duplicated(keep='first')] # remove duplicate rows

        if SHOW_PLOTS:
            df.plot()
            plt.show()

    # save dataframe to csv
    out = os.path.join(out_dir, out_dir[:-1]+'_inclinometer.csv')
    df.to_csv(out)

    return


if __name__ == "__main__":

    os.chdir('/local-scratch/users/aplourde/field_data/')
    sites = glob.glob("*/")

    for site in sites:
        process_all(site)


