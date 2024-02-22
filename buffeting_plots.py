import json
import numpy as np
import scipy.stats
from buffeting import beta_DB_func, beta_0_func
# from create_minigrid_data_from_raw_WRF_500_data import lat_lon_aspect_ratio, bridge_WRF_nodes_coor_func
from straight_bridge_geometry import g_node_coor, p_node_coor, g_s_3D_func
from my_utils import normalize
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import colors
import copy
import pandas as pd
import sympy
import openpyxl
import os

def rad(deg):
    return deg*np.pi/180
def deg(rad):
    return rad*180/np.pi

def get_bridge_node_angles_and_radia_to_plot(ax):
    # rotate from Gs system to Gmagnetic system, where x-axis is aligned with S-N direction:
    rot_angle = rad(10)
    g_node_coor_Gmagnetic = np.einsum('ij,nj->ni', np.transpose(np.array([[np.cos(rot_angle), -np.sin(rot_angle), 0],
                                                                          [np.sin(rot_angle), np.cos(rot_angle), 0],
                                                                          [0, 0, 1]])), g_node_coor)
    ylim = ax.get_ylim()[1] * 0.9
    half_chord = np.max(abs(g_node_coor[:, 0])) / 2
    sagitta = np.max(abs(g_node_coor[:, 1]))
    # Translating grom Gmagnetic to Gcompasscenter, for the coor. sys. to be at the center of the compass
    g_node_coor_Gcompasscenter = np.array([g_node_coor_Gmagnetic[:, 0] - half_chord * np.cos(rot_angle) + sagitta * np.sin(rot_angle),  # the sagitta terms can alternatively be removed
                                           g_node_coor_Gmagnetic[:, 1] + half_chord * np.sin(rot_angle) + sagitta * np.cos(rot_angle),  # the sagitta terms can alternatively be removed
                                           g_node_coor_Gmagnetic[:, 2]]).transpose()
    bridge_node_radius = np.sqrt(g_node_coor_Gcompasscenter[:, 0] ** 2 + g_node_coor_Gcompasscenter[:, 1] ** 2)
    bridge_node_radius_norm = bridge_node_radius / np.max(abs(g_node_coor_Gcompasscenter)) * ylim
    bridge_node_angle = np.arctan2(-g_node_coor_Gcompasscenter[:, 1], g_node_coor_Gcompasscenter[:, 0])
    return bridge_node_angle, bridge_node_radius_norm

# SENSITIVITY ANALYSIS
# Plotting response
def response_polar_plots(symmetry_180_shifts=False, error_bars=True, closing_polygon=False, tables_of_differences=False, shaded_sector=True, show_bridge=True, buffeting_or_static='buffeting', order_by=['skew_approach', 'Analysis', 'g_node_num', 'n_freq', 'SWind', 'KG',  'Method', 'SE', 'FD_type', 'C_Ci_linearity', 'beta_DB']):
    ####################################################################################################################
    # ORGANIZING DATA
    ####################################################################################################################
    # Getting the paths of the results tables
    results_paths_FD = []
    results_paths_TD = []
    all_files_paths = []
    my_path = os.path.join(os.getcwd(), r'results')

    for item in os.listdir(my_path):
        all_files_paths.append(item)

    for path in all_files_paths:
        if path[:16] == "FD_std_delta_max":
            results_paths_FD.append(path)
        if path[:16] == "TD_std_delta_max":
            results_paths_TD.append(path)

    # Getting the DataFrames of the results. Adding column for Analysis type ('TD' or 'FD').
    results_df_list = []
    n_results_FD = len(results_paths_FD)
    n_results_TD = len(results_paths_TD)
    for r in range(n_results_FD):
        df = pd.read_csv(os.path.join(my_path, results_paths_FD[r]))
        df['Analysis'] = 'FD'
        results_df_list.append(df)
    for r in range(n_results_TD):
        df = pd.read_csv(os.path.join(my_path, results_paths_TD[r]))
        df['Analysis'] = 'TD'
        results_df_list.append(df)

    # Merging DataFrames, changing NaNs to string 'NA'
    results_df = pd.concat(results_df_list, ignore_index=True).rename(columns={'Unnamed: 0': 'old_indexes'})
    results_df = results_df.fillna('NA')  # replace nan with 'NA', so that 'NA' == 'NA' when counting betas

    # Re-ordering! Change here: Order first the parameters being studied, and include 'beta_DB' in the end.
    results_df = results_df.sort_values(by=order_by).reset_index(drop=True)

    # DataFrames without results and betas, to find repeated parameters and count number of betas in each case
    if n_results_TD > 0:  # if we have TD results
        list_of_cases_df_repeated = results_df.drop(
            ['old_indexes', 'beta_DB', 'std_max_dof_0', 'std_max_dof_1', 'std_max_dof_2', 'std_max_dof_3',
             'std_max_dof_4', 'std_max_dof_5', 'std_std_max_dof_0', 'std_std_max_dof_1', 'std_std_max_dof_2',
             'std_std_max_dof_3', 'std_std_max_dof_4', 'std_std_max_dof_5', 'static_max_dof_0', 'static_max_dof_1',
             'static_max_dof_2', 'static_max_dof_3', 'static_max_dof_4', 'static_max_dof_5', 'std_static_max_dof_0', 'std_static_max_dof_1',
             'std_static_max_dof_2', 'std_static_max_dof_3', 'std_static_max_dof_4', 'std_static_max_dof_5'], axis=1)  # removing columns
    else:
        list_of_cases_df_repeated = results_df.drop(
            ['old_indexes', 'beta_DB', 'std_max_dof_0', 'std_max_dof_1', 'std_max_dof_2', 'std_max_dof_3',
             'std_max_dof_4', 'std_max_dof_5', 'static_max_dof_0', 'static_max_dof_1', 'static_max_dof_2', 'static_max_dof_3',
             'static_max_dof_4', 'static_max_dof_5'], axis=1)  # removing columns
    # Counting betas of each case
    count_betas = pd.DataFrame({'beta_DB_count': list_of_cases_df_repeated.groupby(
        list_of_cases_df_repeated.columns.tolist()).size()}).reset_index()
    list_of_cases_df = list_of_cases_df_repeated.drop_duplicates().reset_index().rename(
        columns={'index': '1st_result_index'})

    list_of_headers = list(list_of_cases_df.columns.values)

    # list with headers:
    # 'Method', 'n_aero_coef', 'SE', 'FD_type', 'n_modes', 'n_freq',
    # 'g_node_num', 'f_min', 'f_max', 'SWind', 'KG',
    # 'cospec_type',
    # 'damping_ratio', 'damping_Ti', 'damping_Tj',
    # 'Analysis',
    # 'N_seeds', 'dt', 'C_Ci_linearity', 'SE_linearity', 'geometric_linearity'

    list_of_cases_df = pd.merge(list_of_cases_df, count_betas, on=list_of_headers[1:])  # SENSITIVITY ANALYSIS. First header "1st_result_index" not used.

    pd.set_option("display.max_rows", None, "display.max_columns", None, 'expand_frame_repr', False)
    print('Cases available to plot: \n', list_of_cases_df)
    idx_cases_to_plot = eval(input('''Enter list of index numbers from '1st_result_index' to plot:'''))  # choose the index numbers to plot in 1 plot, from '1st result_index' column
    list_of_cases_to_plot_df = list_of_cases_df.loc[list_of_cases_df['1st_result_index'].isin(idx_cases_to_plot)]
    list_of_cases_to_plot_df = list_of_cases_to_plot_df.assign(Method=list_of_cases_to_plot_df['Method'].replace(['2D_fit_free', '2D_fit_cons', '2D_fit_cons_w_CFD', '2D_fit_cons_w_CFD_adjusted', '2D_fit_cons_w_CFD_scale_to_Jul', '2D_fit_cons_2', 'cos_rule', '2D'], ['Free fit', 'SOH', 'SOH+CFD', 'SOH+CFD+Jul.', 'SOH+CFD scaled to Jul.','2-var. constr. fit (2)', 'Cosine rule', '2D']))
    list_of_cases_to_plot_df = list_of_cases_to_plot_df.assign(FD_type=list_of_cases_to_plot_df['FD_type'].replace(['3D_Zhu', '3D_Scanlan','3D_full'], ['(QS) Zhu', '(QS) Scanlan', '(QS) full']))
    ####################################################################################################################
    # PLOTTING
    ####################################################################################################################
    from cycler import cycler
    angle_idx = list(list_of_cases_to_plot_df['1st_result_index'])
    angle_idx = [list(range(angle_idx[i], angle_idx[i]+list_of_cases_to_plot_df['beta_DB_count'].iloc[i])) for i in range(len(angle_idx))]

    if buffeting_or_static == 'buffeting':
        str_dof = ["Max. $\sigma_x$ $[m]$",
                   "Max. $\sigma_y$ $[m]$",
                   "Max. $\sigma_z$ $[m]$",
                   "Max. $\sigma_{rx}$ $[\degree]$",
                   "Max. $\sigma_{ry}$ $[\degree]$",
                   "Max. $\sigma_{rz}$ $[\degree]$"]
    elif buffeting_or_static == 'static':
        str_dof = ["Max. $|\Delta_x|$ $[m]$",
                   "Max. $|\Delta_y|$ $[m]$",
                   "Max. $|\Delta_z|$ $[m]$",
                   "Max. $|\Delta_{rx}|$ $[\degree]$",
                   "Max. $|\Delta_{ry}|$ $[\degree]$",
                   "Max. $|\Delta_{rz}|$ $[\degree]$"]

    str_dof2 = ['x','y','z','rx','ry','rz']

    new_colors = [plt.get_cmap('jet')(1. * i / len(idx_cases_to_plot)) for i in range(len(idx_cases_to_plot))]
    # # 3 colors for FD
    # custom_cycler = (cycler(color=['orange', 'blue', 'green', 'cyan', 'cyan', 'cyan', 'gold', 'gold', 'gold', 'red', 'red', 'red']) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['-', '-', ':', '-.', '--', '--', '-', '--', '--', '-', '--', '--']) +
    #                  cycler(lw=[3.0, 2.5, 2.55, 1.2, .8, .8, 1.8, .8, .8, 1.8, .8, .8]) +
    #                  cycler(alpha=[0.6, 0.5, 0.7, 0.5, 0.5, 0.5, 0.7, 0.5, 0.5, 0.7, 0.5, 0.5]))
    # 1 TD case with +- STD of STD
    # custom_cycler = (cycler(color=['orange', 'darkorange', 'darkorange', 'darkorange']) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['-', '-.', '--', '--']) +
    #                  cycler(lw=[4.0, 2.0, 1.5, 1.5]) +
    #                  cycler(alpha=[0.6, 0.9, 0.9, 0.9]))
    # FD vs 1 TD case with +- STD of STD
    # lineweight_list = [3.0, 2.8, 1.5, 2., 2.]
    # custom_cycler = (cycler(color=['brown', 'deepskyblue', 'gold', 'darkorange', 'darkorange']) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['-', '-', '-', ':', '-.']) +
    #                  cycler(lw=lineweight_list) +
    #                  cycler(alpha=[0.8, 0.4, 0.8, 0.8, 0.8]))
    # FD aero method with both FD and TD
    lineweight_list = [2., 2., 2., 2.]
    custom_cycler = (cycler(color=['dodgerblue', 'gold', 'blue', 'orange']) +
                     #cycler(color=new_colors) +
                     cycler(linestyle=['-', '-', '--', '--']) +
                     cycler(lw=lineweight_list) +
                     cycler(alpha=[0.8, 0.8, 0.8, 0.8]))
    # # Sensitivity
    # custom_cycler = (cycler(color=['cyan', 'orange', 'red', 'blue', 'magenta', 'blue', 'red']) +
    #                  # cycler(color=new_colors) +
    #                  cycler(linestyle=['solid', 'dashed', 'dashdot', 'dotted', 'solid', 'dashed', 'dashdot']) +
    #                  cycler(lw=[1, 1, 1., 1, 1, 1., 1]) +
    #                  cycler(alpha=[0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6]))
    # FD aero method:
    # lineweight_list = [2., 2., 2., 2.]
    # custom_cycler = (cycler(color=['gold', 'brown', 'green', 'blue', ]) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['--', '-', '-.', (0, (3, 1.5, 1, 1.5, 1, 1.5))]) +
    #                  cycler(lw=lineweight_list) +
    #                  cycler(marker=["o"]*len(lineweight_list)) +
    #                  cycler(markersize=np.array(lineweight_list)*1.2) +
    #                  cycler(alpha=[0.8, 0.8, 0.8, 0.4]))
    # FD approach:
    # lineweight_list = [2., 2., 2., 2.]
    # custom_cycler = (cycler(color=['gold','green','brown', 'blue', ]) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['--','-.', '-', (0, (3, 1.5, 1, 1.5, 1, 1.5))]) +
    #                  cycler(lw=lineweight_list) +
    #                  cycler(marker=["o"]*len(lineweight_list)) +
    #                  cycler(markersize=np.array(lineweight_list)*1.2) +
    #                  cycler(alpha=[0.8, 0.8, 0.8, 0.4]))
    # Only one FD case:
    # lineweight_list = [2., 2., 2., 2.]
    # custom_cycler = (cycler(color=['brown', 'green', 'gold', 'blue', ]) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['-', '-.', '--', (0, (3, 1.5, 1, 1.5, 1, 1.5))]) +
    #                  cycler(lw=lineweight_list) +
    #                  cycler(marker=["o"]*len(lineweight_list)) +
    #                  cycler(markersize=np.array(lineweight_list)*1.2) +
    #                  cycler(alpha=[0.8, 0.8, 0.8, 0.4]))
    # SE forces:
    # lineweight_list = [2.0, 3.5, 2.5, 1.5, 2.]
    # custom_cycler = (cycler(color=['deepskyblue', 'gold', 'green', 'brown', 'darkorange']) +
    #                  #cycler(color=new_colors) +
    #                  cycler(linestyle=['-', '-', '--', ':', '-.']) +
    #                  cycler(lw=lineweight_list) +
    #                  cycler(marker=["o"]*len(lineweight_list)) +
    #                  cycler(markersize=np.array(lineweight_list)*1.2) +
    #                  cycler(alpha=[0.4, 0.8, 0.8, 0.8, 0.8]))

    for dof in [0,1,2,3,4,5]:
        plt.figure(figsize=(3.7, 3.7), dpi=600)
        ax = plt.subplot(111, projection='polar')
        ax.set_prop_cycle(custom_cycler)
        k = -1 # counter
        # Use this for FD only:
        for _, (_, aero_coef_method, n_aero_coef, include_SE, flutter_derivatives_type, n_modes, n_freq, g_node_num, f_min, f_max, include_sw, include_KG, skew_approach, f_array_type,
                make_M_C_freq_dep, dtype_in_response_spectra, Nw_idx, Nw_or_equiv_Hw, cospec_type, damping_ratio, damping_Ti, damping_Tj, analysis_type, _) in list_of_cases_to_plot_df.iterrows():
        # Use this for TD only:
        # for _, (_, aero_coef_method, n_aero_coef, include_SE, flutter_derivatives_type, n_modes, n_freq, g_node_num, f_min, f_max, include_sw, include_KG, skew_approach,
        #         f_array_type, make_M_C_freq_dep, dtype_in_response_spectra, cospec_type,
        #         damping_ratio, damping_Ti, damping_Tj, analysis_type, n_seeds, dt, C_Ci_linearity, SE_linearity, geometric_linearity, _) in list_of_cases_to_plot_df.iterrows():
        # Use this for FD + TD:
        # for _, (_, aero_coef_method, n_aero_coef, include_SE, flutter_derivatives_type, n_modes, n_freq, g_node_num, f_min, f_max, include_sw, include_KG, skew_approach, f_array_type,
        #         make_M_C_freq_dep, dtype_in_response_spectra, Nw_idx, Nw_or_equiv_Hw, cospec_type,
        #         damping_ratio, damping_Ti, damping_Tj, analysis_type, n_seeds, dt, C_Ci_linearity, SE_linearity, geometric_linearity, where_to_get_wind, _) in list_of_cases_to_plot_df.iterrows():

            k += 1  # starts with 0
            # str_plt_0 = aero_coef_method[:6] + '. '
            # str_plt_1 = 'Ca: ' + str(n_aero_coef)[:1] + '. '
            # str_plt_2 = 'w/ SE. ' if include_SE else 'w/o SE. '
            # str_plt_3 = flutter_derivatives_type + '.' if include_SE else ''
            # str_plt = str_plt_0 + str_plt_1 + str_plt_2 + str_plt_3
            if analysis_type == 'FD':
                # str_plt = 'Frequency-domain'
                # str_plt = str(skew_approach) + '.  MD: ' + str(include_SE)[0]
                # str_plt = str(aero_coef_method)
                # str_plt = str(skew_approach)
                # str_plt = str(skew_approach) + '. ' + str(n_aero_coef)
                if not include_SE:
                    str_plt = 'No self-excited forces'
                if include_SE:
                    # str_plt = str(flutter_derivatives_type)
                    str_plt = str(aero_coef_method) + ' (FD)'
                # str_plt = r'Frequency-domain'
                # str_plt = str(int(n_freq))
                # str_plt = str(int(g_node_num))
            if analysis_type == 'TD':
                str_plt = str(aero_coef_method) + ' (TD)'
                # str_plt = r'Time-domain: $\mu$ ('+ u"\u00B1" +' $\sigma$)'
                # if C_Ci_linearity == 'L':
                #     str_plt = 'Linear time-domain'
                # elif C_Ci_linearity == 'NL':
                #     str_plt = 'Non-linear time-domain'
            angle = np.array(results_df['beta_DB'][angle_idx[k][0]:angle_idx[k][-1]+1])
            if buffeting_or_static == 'buffeting':
                radius = np.array(results_df['std_max_dof_' + str(dof)][angle_idx[k][0]:angle_idx[k][-1]+1])
                if n_results_TD > 0 and error_bars and analysis_type=='TD': # Include error_bars
                    radius_std = np.array(results_df['std_std_max_dof_' + str(dof)][angle_idx[k][0]:angle_idx[k][-1]+1])
            if buffeting_or_static == 'static':
                radius = np.array(results_df['static_max_dof_' + str(dof)][angle_idx[k][0]:angle_idx[k][-1]+1])
                if n_results_TD > 0 and error_bars and analysis_type=='TD': # Include error_bars
                    radius_std = np.array(results_df['std_static_max_dof_' + str(dof)][angle_idx[k][0]:angle_idx[k][-1]+1])

            if dof >= 3:
                import copy
                radius = deg(copy.deepcopy(radius))  # converting from radians to degrees!
                if n_results_TD > 0 and error_bars and analysis_type == 'TD':
                    radius_std = deg(copy.deepcopy(radius_std))  # converting from radians to degrees!
            if symmetry_180_shifts:
                angle = np.append(angle, angle+np.pi)
                radius = np.append(radius, radius)
                if n_results_TD > 0 and error_bars and analysis_type=='TD':
                    radius_std = np.append(radius_std, radius_std)  # for error bars
            if closing_polygon:
                angle = np.append(angle, angle[0])  # Closing the polygon, adding same value to end:
                radius = np.append(radius, radius[0])  # Closing the polygon, adding same value to end:
            if not (n_results_TD > 0 and analysis_type=='TD' and error_bars):  # plot only if FD or if in TD no error bars are desired
                ax.plot(angle, radius, label=str_plt) #, zorder=0.7)
            else:
                if closing_polygon:
                    radius_std = np.append(radius_std, radius_std[0])  # Closing the polygon, adding same value to end:
                ax.errorbar(angle, radius, yerr=radius_std, label=str_plt) #, zorder=0.7)
                # ax.plot(angle, radius - radius_std, label=r'Time-domain: $\mu$ '+u"\u00B1"+' $\sigma$') #, zorder=0.7)
                # ax.plot(angle, radius + radius_std) #, zorder=0.7)
        if shaded_sector:
            ylim = ax.get_ylim()
            # Shade interpolation area:
            ax.fill_between(np.linspace(rad(100-30), rad(100+30), 100), ylim[0], ylim[1], color='lime', alpha=0.1, edgecolor='None') #, zorder=0.8)
            ax.fill_between(np.linspace(rad(280-30), rad(280+30), 100), ylim[0], ylim[1], color='lime', alpha=0.1, edgecolor='None', label='Domain of available ' + r'$C_{i}$' + ' data') #, zorder=0.8)
            # Shade extrapolation area:
            ax.fill_between(np.linspace(rad(100+30), rad(280-30), 100), ylim[0], ylim[1], color='grey', alpha=0.1, edgecolor='None') #, zorder=0.8)
            ax.fill_between(np.linspace(rad(280+30), rad(360)   , 100), ylim[0], ylim[1], color='grey', alpha=0.1, edgecolor='None') #, zorder=0.8)
            ax.fill_between(np.linspace(rad(0)     , rad(100-30), 100), ylim[0], ylim[1], color='grey', alpha=0.1, edgecolor='None', label='Domain of ' + r'$C_{i}$' + ' extrapolation') #, zorder=0.8)
        if show_bridge:
            bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
            ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.5, color='black', marker="None", label='Bridge axis')#,zorder=k+1)

        ax.grid(True)
        # ax.legend(bbox_to_anchor=(1.63,0.93), loc="upper right", title='Analysis:')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_title(str_dof[dof], va='bottom')
        # ax.set_title(str_dof[dof]+'\n (Fitting: ' + str(aero_coef_method)+')', va='bottom')
        # ax.set_title('\n Sensitivity: No. frequency bins\n'+str_dof[dof][:-2], va='bottom')
        # ax.set_title('\n Sensitivity: No. girder nodes\n'+str_dof[dof][:-2], va='bottom')

        plt.tight_layout()

        plt.savefig(r'results\Polar_std_delta_local_' + str(buffeting_or_static) + '_' + str_dof2[dof] +'_Spec-' + str(cospec_type) + \
                    '_zeta-' + str(damping_ratio) + '_Ti-' + str(damping_Ti) + '_Tj-' + str(damping_Tj) + '_Nodes-' + \
                    str(g_node_num) + '_Modes-' + str(n_modes) + '_FD-f-' + str(f_min) + '-' + str(f_max) + \
                    '-' + str(n_freq) + '_NAeroCoef-' + str(n_aero_coef) + '.png')

        handles, labels = plt.gca().get_legend_handles_labels()
        # order = [0, 3, 1, 4, 2, 5]
        # FD skew approach:
        order = list(range(len(handles)))
        # order = [0, 3, 1, 4, 2]
        # FD aero fit method:
        # order = [3,0,2,1,4,5,6]
        # order = list(range(len(handles)))
        # SE:
        # order = list(range(len(handles)))
        # FD vs 1 TD:
        # order = [0, 4, 1, 2, 3]  # with shaded sectors
        # order = [0, 2, 3, 1]  # without shaded sectors
        # # N aero coef:
        # labels[0] = '(3D) ' + r'$[0,C_y,C_z,C_{rx},0,0]$'
        # labels[1] = '(3D) ' + r'$[C_x,C_y,C_z,C_{rx},0,0]$'
        # labels[2] = '(3D) ' + r'$[C_x,C_y,C_z,C_{rx},C_{ry},C_{rz}]$'
        # aero Method:
        # labels = [l.replace('Cosine rule', '(3D) Univar. fit + Cosine rule') for l in labels]
        # labels = [l.replace('2D', '(3D) Univar. fit + 2D approach') for l in labels]
        # labels = [l.replace('Free fit', '(3D) Free bivariate fit') for l in labels]
        # labels = [l.replace('Constrained fit', '(3D) Constrained bivariate fit') for l in labels]

        legend = plt.legend([handles[idx] for idx in order], [labels[idx] for idx in order], bbox_to_anchor=(10.63,0.93)) #, ncol=1)

        def export_legend(legend, filename=r'results\legend.png', expand=[-5, -5, 5, 5]):
            fig = legend.figure
            fig.canvas.draw()
            bbox = legend.get_window_extent()
            bbox = bbox.from_extents(*(bbox.extents + np.array(expand)))
            bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
            fig.savefig(filename, dpi="figure", bbox_inches=bbox)
        export_legend(legend)
        plt.close()

    if tables_of_differences:
        # Table of differences
        num_cases = len(list_of_cases_df)
        num_betas = list_of_cases_df.iloc[0]['beta_DB_count']
        table_max_diff_all_betas = pd.DataFrame()
        table_all_diff = pd.DataFrame(np.zeros((num_cases*num_betas, num_cases*6))*np.NaN)
        table_all_diff.columns = ['std_max_dof_0', 'std_max_dof_1', 'std_max_dof_2', 'std_max_dof_3', 'std_max_dof_4', 'std_max_dof_5']*num_cases
        table_all_diff['Case'] = 'N/A'  # adding a new column at the end.
        table_all_diff.loc[-1] = 'N/A'  # apparently this adds a new row to the end..... . ... ..
        assert all([num_betas == list_of_cases_df.iloc[i]['beta_DB_count'] for i in range(len(list_of_cases_df))])  # all cases have same number of betas
        betas_deg_df = np.round(results_df['beta_DB'].iloc[0:num_betas] * 180 / np.pi)
        for i in range(num_cases):
            str_case_i = list_of_cases_df.iloc[i]['skew_approach'] + '. MD: ' + str(list_of_cases_df.iloc[i]['SE'])[0]
            if list_of_cases_df.iloc[i]['SE']:
                str_case_i += '. ' + list_of_cases_df.iloc[i]['FD_type']
            for j in range(num_cases):
                if i >= j:
                    str_case_j = list_of_cases_df.iloc[j]['skew_approach'] + '. MD: ' + str(list_of_cases_df.iloc[j]['SE'])[0]
                    if list_of_cases_df.iloc[j]['SE']:
                        str_case_j += '. ' + list_of_cases_df.iloc[j]['FD_type']
                    results_case_i = results_df.iloc[i * num_betas: i * num_betas + num_betas][['std_max_dof_0', 'std_max_dof_1', 'std_max_dof_2', 'std_max_dof_3', 'std_max_dof_4', 'std_max_dof_5']].reset_index(drop=True)
                    results_case_j = results_df.iloc[j * num_betas: j * num_betas + num_betas][['std_max_dof_0', 'std_max_dof_1', 'std_max_dof_2', 'std_max_dof_3', 'std_max_dof_4', 'std_max_dof_5']].reset_index(drop=True)
                    results_diff_ij = (results_case_i - results_case_j)/results_case_j * 100
                    results_diff_ij_arr = np.array(results_diff_ij)
                    table_all_diff.iloc[i * num_betas: i * num_betas + num_betas, j*6:j*6+6] = results_diff_ij_arr
                    table_all_diff.iloc[i * num_betas: i * num_betas + num_betas,-1] = [str_case_i] * num_betas  # naming the cases in the last column
                    table_all_diff.iloc[-1, j*6:j*6+6] = [str_case_j]*6   # naming the cases in the last row
                    # Table of maximum differences
                    if i > j:
                        if not (('3D' in str_case_i and '2D' in str_case_j) or ('2D' in str_case_i and '3D' in str_case_j) or ('MD: T' in str_case_i and 'MD: F' in str_case_j) or ('MD: F' in str_case_i and 'MD: T' in str_case_j)):  # put your conditions here to compare what you want
                            max_diff_all_betas_ij = pd.DataFrame(abs(results_diff_ij).max(axis=0))
                            max_diff_all_betas_ij.columns = [ '(' + str_case_i + ')   VS   (' + str_case_j + ')']
                            table_max_diff_all_betas = pd.concat([table_max_diff_all_betas, max_diff_all_betas_ij], axis=1)
        table_all_diff.insert(0,"beta[deg]", betas_deg_df.tolist()*num_cases + ['Cases:'])
        table_max_diff_all_betas = table_max_diff_all_betas.T
        from time import gmtime, strftime
        table_all_diff.to_csv(r'results\Table_of_all_differences_between_all_cases_' + strftime("%Y-%m-%d_%H-%M-%S", gmtime()) + '.csv',index = False)
        table_max_diff_all_betas.to_csv(r'results\Table_of_the_maximum_difference_for_pairs_of_cases_' + strftime("%Y-%m-%d_%H-%M-%S", gmtime()) + '.csv')


# response_polar_plots(symmetry_180_shifts=False, error_bars=True, closing_polygon=True, tables_of_differences=False, shaded_sector=False, show_bridge=True, buffeting_or_static='static', order_by=['Analysis', 'Method', 'n_freq', 'beta_DB'])
response_polar_plots(symmetry_180_shifts=False, error_bars=True, closing_polygon=True, tables_of_differences=False, shaded_sector=False, show_bridge=True, buffeting_or_static='buffeting', order_by=['Analysis', 'Method', 'n_freq', 'beta_DB'])
# # response_polar_plots(symmetry_180_shifts=False, error_bars=False, closing_polygon=True, tables_of_differences=False, shaded_sector=True, show_bridge=True, order_by=['skew_approach', 'Analysis', 'g_node_num', 'n_freq', 'SWind', 'KG',  'Method', 'SE', 'FD_type', 'C_Ci_linearity', 'f_array_type', 'make_M_C_freq_dep', 'dtype_in_response_spectra', 'beta_DB'])
# # response_polar_plots(symmetry_180_shifts=False, error_bars=True, closing_polygon=True, tables_of_differences=False, shaded_sector=True, show_bridge=True, order_by=['skew_approach', 'Analysis', 'g_node_num', 'n_freq', 'SWind', 'KG',  'Method', 'SE', 'FD_type', 'n_aero_coef', 'make_M_C_freq_dep', 'beta_DB'])


def produce_response_tables_of_differences(in_csv_path, out_csv_path, method_1, method_2):
    """
    Produces a table comparing the relative changes in response from method_1 to method_2
    """
    df = pd.read_csv(in_csv_path)
    beta_DB = df[df['Method'] == method_1]['beta_DB']
    assert np.allclose(df[df['Method'] == method_1]['beta_DB'], df[df['Method'] == method_2]['beta_DB']), 'Method 1 and 2 have different sizes of betas which will cause problems here'
    beta_0 = beta_0_func(beta_DB)
    df_out_3 = pd.DataFrame({'beta_DB': beta_DB, 'beta_0': beta_0})  # named 3, instead of 1, to not confuse w/ method 1
    df_out_4 = pd.DataFrame({'keys':['diff_of_max', 'max_1', 'max_2', 'beta_max_1', 'beta_max_2',
                                     'max_of_diff', 'beta_max_of_diff']})  # named 4, instead of 2, to not confuse w/ method 2
    df_out_5 = pd.DataFrame({'keys':['diff_of_max', 'diff_beta0_0', 'diff_beta0_30', 'diff_beta0_60', 'diff_beta0_90']})

    for type in ['static_max_dof_', 'std_max_dof_']:
        for d in ["0","1","2","3","4","5"]:
            # Getting difference of the two maximums (diff between max of method 1 and max of method 2)
            dof = type + d
            resp_1 = np.array(df[df['Method'] == method_1][dof])
            resp_2 = np.array(df[df['Method'] == method_2][dof])
            rel_change = (resp_2 - resp_1) / np.abs(resp_1)
            df_out_3[f'diff_{dof}'] = rel_change

            idx_absmax_1 = df[df['Method'] == method_1][dof].abs().idxmax()
            idx_absmax_2 = df[df['Method'] == method_2][dof].abs().idxmax()
            absmax_1 = df[df['Method'] == method_1][dof][idx_absmax_1]
            absmax_2 = df[df['Method'] == method_2][dof][idx_absmax_2]
            beta_absmax_1 = df[df['Method'] == method_1]['beta_DB'][idx_absmax_1]
            beta_absmax_2 = df[df['Method'] == method_2]['beta_DB'][idx_absmax_2]
            diff_of_absmax = (absmax_2 - absmax_1) / np.abs(absmax_1)
            idx_absmax_of_diff = df_out_3[f'diff_{dof}'].abs().idxmax()
            absmax_of_diff = df_out_3[f'diff_{dof}'][idx_absmax_of_diff]  # Less relevant: Getting maximum of the all differences (one difference per beta)
            beta_absmax_of_diff = df_out_3['beta_DB'][idx_absmax_of_diff]
            df_out_4[dof] = [diff_of_absmax, absmax_1, absmax_2, beta_absmax_1, beta_absmax_2,
                             absmax_of_diff, beta_absmax_of_diff]

            df['beta_0'] = beta_0_func(df['beta_DB'])
            diff_value_beta0_b_all = {}
            for b_deg in [0, 30, 60, 90]:
                b_rad = rad(b_deg)
                idx_1_beta0_b = (df[df['Method'] == method_1]['beta_0'] - b_rad).abs().idxmin()
                idx_2_beta0_b = (df[df['Method'] == method_2]['beta_0'] - b_rad).abs().idxmin()
                value_1_beta0_b = df[df['Method'] == method_1][dof][idx_1_beta0_b]
                value_2_beta0_b = df[df['Method'] == method_2][dof][idx_2_beta0_b]
                diff_value_beta0_b = (value_2_beta0_b - value_1_beta0_b) / np.abs(value_1_beta0_b)
                diff_value_beta0_b_all[f'beta0_{b_deg}'] = diff_value_beta0_b
            df_out_5[dof] = [diff_of_absmax, diff_value_beta0_b_all['beta0_0'], diff_value_beta0_b_all['beta0_30'],
                             diff_value_beta0_b_all['beta0_60'], diff_value_beta0_b_all['beta0_90']]

    with pd.ExcelWriter(out_csv_path, engine='openpyxl') as writer:
        df_out_3.to_excel(writer, sheet_name='all_angles')
        df_out_4.to_excel(writer, sheet_name='other')
        df_out_5.to_excel(writer, sheet_name='summary')


produce_response_tables_of_differences(in_csv_path = r"C:\Users\bercos\PycharmProjects\benchmark_straight_bridge\results\standard straight bridge\FD_std_delta_max_2024-02-06_18-27-22.csv",
                                       out_csv_path = r'results\compare_response_differences_straight.xlsx',
                                       method_1 = r"cos_rule_aero_coefs_Ls_2D_fit_cons_polimi-K12-G-L-TS-SVV.xlsx",
                                       method_2 = r"aero_coefs_Ls_2D_fit_cons_polimi-K12-G-L-TS-SVV.xlsx")
produce_response_tables_of_differences(in_csv_path = r"C:\Users\bercos\PycharmProjects\benchmark_straight_bridge\results\R 500\FD_std_delta_max_2024-02-06_20-27-35.csv",
                                       out_csv_path = r'results\compare_response_differences_R500.xlsx',
                                       method_1 = r"cos_rule_aero_coefs_Ls_2D_fit_cons_polimi-K12-G-L-TS-SVV.xlsx",
                                       method_2 = r"aero_coefs_Ls_2D_fit_cons_polimi-K12-G-L-TS-SVV.xlsx")
produce_response_tables_of_differences(in_csv_path = r"C:\Users\bercos\PycharmProjects\benchmark_straight_bridge\results\R 1000\FD_std_delta_max_2024-02-06_21-42-32.csv",
                                       out_csv_path = r'results\compare_response_differences_R1000.xlsx',
                                       method_1 = r"cos_rule_aero_coefs_Ls_2D_fit_cons_polimi-K12-G-L-TS-SVV.xlsx",
                                       method_2 = r"aero_coefs_Ls_2D_fit_cons_polimi-K12-G-L-TS-SVV.xlsx")


def plot_contourf_spectral_response(f_array, S_delta_local, g_node_coor, S_by_freq_unit='rad', zlims_bool=False, cbar_extend='min', filename='Contour_', idx_plot=[1,2,3]):
    """
    S_delta_local: shape(n_freq, n_nodes, n_dof)
    """
    g_s_3D = g_s_3D_func(g_node_coor)
    x = np.round(g_s_3D)
    y = f_array
    x, y = np.meshgrid(x, y)
    for i in idx_plot:
        idx_str = ['x','y','z','rx','ry','rz'][i]
        idx_str_2 = ['$[m^2/Hz]$','$[m^2/Hz]$','$[m^2/Hz]$','$[\degree^2/Hz]$','$[\degree^2/Hz]$','$[\degree^2/Hz]$'][i]
        plt.figure(figsize=(4, 3), dpi=400)
        plt.title(r'$S_{\Delta_{'+idx_str+'}}$'+' '+idx_str_2)
        cmap = plt.get_cmap(matplotlib.cm.viridis)
        vmin = [10**-3,10**-2,10**-3,10**-3,10**-3,10**-3][i]
        factor = 2*np.pi if S_by_freq_unit == 'rad' else 1
        z = np.real(S_delta_local[:, :, i]) * factor  # This is to change the spectral units from m^2/rad to m^2/Hz
        if i >= 3:
            z = copy.deepcopy(z) / np.pi**2 * 180**2  # This is to change the spectral units from rad^2/Hz to degree^2/Hz
        vmax = np.max(z)
        if zlims_bool:
            zlims = [None, [1E-2, 8.9E3], [1E-3,4.4E-1], [1E-3, 3.7E-1], [None], [None]]
            vmax = zlims[i][1]
        levels_base_outer = np.power(10, np.arange(np.floor(np.log10(vmin)), np.ceil(np.log10(vmax))+1))
        levels_base_inner = np.power(10, np.arange(np.ceil(np.log10(vmin)), np.floor(np.log10(vmax))+1))
        levels = np.logspace(np.log10(levels_base_outer[0]), np.log10(vmax), num=200)
        plt.contourf(x, y, z, cmap=cmap, extend=cbar_extend, levels=levels, norm=colors.LogNorm(min(levels),vmax))
        plt.ylabel('Frequency [Hz]')
        plt.yscale('log')
        plt.ylim([0.002, 0.5])
        plt.xlabel('Along arc length [m]')
        plt.xticks([0,2500,5000])

        plt.colorbar(ticks=levels_base_inner)
        plt.tight_layout()
        plt.savefig(r'results\\' + str(filename) + idx_str + ".png")
        plt.close()

def plot_contourf_time_history_response(u_loc, time_array, g_node_coor, filename='Contour_TimeHistory_', idx_plot=[1,2,3]):
    """
    S_delta_local: shape(n_freq, n_nodes, n_dof)
    """
    import matplotlib
    from straight_bridge_geometry import g_s_3D_func
    import copy
    g_s_3D = g_s_3D_func(g_node_coor)
    dt = time_array[1] - time_array[0]
    g_node_num = len(g_s_3D)
    x_base = np.round(g_s_3D)
    for i in idx_plot:
        idx_str = ['x','y','z','rx','ry','rz'][i]
        idx_str_2 = ['$[m]$','$[m]$','$[m]$','$[\degree]$','$[\degree]$','$[\degree]$'][i]
        plt.figure(figsize=(4, 3), dpi=400)
        plt.title(r'$\Delta_{'+idx_str+'}$'+' '+idx_str_2)
        cmap = plt.get_cmap(matplotlib.cm.seismic)
        time_idx_max_response = int(np.where(u_loc[i,:,:g_node_num]==np.max(u_loc[i,:,:g_node_num]))[0])
        dof_eigen_period_of_interest = [100, 100, 6, 6, 6, 6][i]
        time_window_idxs = [time_idx_max_response - int(dof_eigen_period_of_interest*10/dt), time_idx_max_response + int(dof_eigen_period_of_interest*10/dt)]
        z = u_loc[i,time_window_idxs[0]:time_window_idxs[1],:g_node_num]  # excluding pontoon nodes
        y = time_array[time_window_idxs[0]:time_window_idxs[1]]
        x, y = np.meshgrid(x_base, y)
        if i >= 3:
            z = copy.deepcopy(z) / np.pi * 180  # This is to change the spectral units from rad^2/Hz to degree^2/Hz
        vabsmax = np.max(np.abs(z))
        levels = np.linspace(-vabsmax, vabsmax, num=201)
        plt.contourf(x, y, z, cmap=cmap, levels=levels)
        plt.ylabel('Time [s]')
        plt.xlabel('Along arc length [m]')
        plt.xticks([0,2500,5000])
        vabsmax_round = np.round(vabsmax,1)
        # ticks = np.round(np.linspace(-vabsmax_round, vabsmax_round, num=10),1)
        # plt.colorbar(ticks = ticks)
        plt.colorbar()
        ax = plt.gca()
        ax.spines['bottom'].set_linestyle((0, (5, 5)))
        ax.spines['top'].set_linestyle((0, (5, 5)))
        plt.tight_layout()
        plt.savefig(r'results\\' + str(filename) + idx_str + ".png")
        plt.close()
    pass

def time_domain_plots():
    from straight_bridge_geometry import g_node_coor
    my_path = os.path.join(os.getcwd(), r'results')
    u_loc_path = []
    TD_df_path = []  # to obtain the time step dt
    for item in os.listdir(my_path):
        if item[:5] == 'u_loc':
            u_loc_path.append(item)
        elif item[:6] == 'TD_std':
            TD_df_path.append(item)
    idx_u_loc = -1
    idx_TD_std = -1
    TD_df = pd.read_csv(my_path + r"\\" + TD_df_path[idx_TD_std])
    dt = float(TD_df['dt'])  # obtaining the time step dt
    g_node_num = int(TD_df['g_node_num'])  # obtaining the time step dt
    u_loc = np.loadtxt(my_path + r"\\" + u_loc_path[idx_u_loc])
    u_loc = np.array([u_loc[:, 0::6], u_loc[:, 1::6], u_loc[:, 2::6], u_loc[:, 3::6], u_loc[:, 4::6], u_loc[:, 5::6]])  # convert to shape(n_dof, time, n_nodes)
    time_array = np.arange(0, len(u_loc[0])) * dt

    # Plotting time history for y
    plot_contourf_time_history_response(u_loc, time_array, g_node_coor, filename='Contour_TimeHistory_', idx_plot=[1, 2, 3])

    from scipy import signal
    Pxx_den = []
    fs = 1/dt
    nperseg = 6000
    f = signal.welch(u_loc[0,:, 0], fs=fs, nperseg=nperseg)[0]
    # f = signal.periodogram(u_loc[0,:, 0], fs=fs)[0]
    for d in range(6):
        Pxx_den_1_dof_all_nodes = []
        for n in range(g_node_num):
            Pxx_den_1_dof_all_nodes.append(signal.welch(u_loc[d,:, n], fs=fs, nperseg=nperseg)[1])
            # Pxx_den_1_dof_all_nodes.append(signal.periodogram(u_loc[d, :, n], fs=fs)[1])
        Pxx_den.append(Pxx_den_1_dof_all_nodes)
    Pxx_den = np.moveaxis(np.moveaxis(np.array(Pxx_den), 0, -1), 0,1)  # convert to shape(n_freq, n_nodes, n_dof)
    plot_contourf_spectral_response(f_array=f, S_delta_local=Pxx_den, g_node_coor=g_node_coor, S_by_freq_unit='Hz', zlims_bool=True, cbar_extend='both', filename='Contour_TD_', idx_plot=[1,2,3])
# time_domain_plots()


def Nw_tables(folder_suffix='3D'):
    """Inhomogeneous wind static & buffeting response tables"""
    matplotlib.rcParams.update({'font.size': 14})  # was 12 in previous PhD theses. now set to 14
    n_g_nodes = len(g_node_coor)
    # Getting the Nw wind properties into the same df
    my_Nw_path = os.path.join(os.getcwd(), r'intermediate_results', f'static_wind_{folder_suffix}')
    n_Nw_sw_cases = len(os.listdir(my_Nw_path))
    Nw_dict_all, Nw_D_loc, Hw_D_loc, Nw_U_bar_RMS, Nw_U_bar, Hw_U_bar, Hw_U_bar_RMS, Nw_beta_0,  Hw_beta_0, Nw_Ii, Hw_Ii = [],[],[],[],[],[],[],[],[],[],[]  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(n_Nw_sw_cases):
        Nw_path = os.path.join(my_Nw_path, f'Nw_dict_{i}.json')
        with open(Nw_path, 'r') as f:
            Nw_dict_all.append(json.load(f))
            Nw_U_bar.append(np.array(Nw_dict_all[i]['Nw_U_bar']))
            Hw_U_bar.append(np.array(Nw_dict_all[i]['Hw_U_bar']))
            Nw_U_bar_RMS.append(np.sqrt(np.mean(np.array(Nw_dict_all[i]['Nw_U_bar'])**2)))
            Hw_U_bar_RMS.append(np.sqrt(np.mean(np.array(Nw_dict_all[i]['Hw_U_bar'])**2)))
            Nw_beta_0.append(np.array(Nw_dict_all[i]['Nw_beta_0']))
            Hw_beta_0.append(np.array(Nw_dict_all[i]['Hw_beta_0']))
            Nw_D_loc.append(np.array(Nw_dict_all[i]['Nw_D_loc']))
            Hw_D_loc.append(np.array(Nw_dict_all[i]['Hw_D_loc']))
            Nw_Ii.append(np.array(Nw_dict_all[i]['Nw_Ii']))
            Hw_Ii.append(np.array(Nw_dict_all[i]['Hw_Ii']))

    def func(x, dof):
        """converts results in radians to degrees, if dof is an angle"""
        if dof >= 3:
            return deg(x)
        else:
            return x

    def mapRange(value, in_bound, out_bound):
        inMin, inMax = in_bound
        outMin, outMax = out_bound
        return outMin + (((value - inMin) / (inMax - inMin)) * (outMax - outMin))
    ###################### BUFFETING #############################
    # Getting the Nw wind properties into the same df
    my_Nw_buf_path = os.path.join(os.getcwd(), r'intermediate_results', f'buffeting_{folder_suffix}')
    n_Nw_buf_cases = np.max([int(''.join(i for i in f if i.isdigit())) for f in os.listdir(my_Nw_buf_path)]) + 1  # use +1 to count for the 0.
    std_delta_local = {'Nw':np.nan*np.zeros((n_Nw_buf_cases, n_g_nodes, 6)),
                       'Hw':np.nan*np.zeros((n_Nw_buf_cases, n_g_nodes, 6)),}  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(n_Nw_buf_cases):
        Nw_path = os.path.join(my_Nw_buf_path, f'Nw_buffeting_{i}.json')
        Hw_path = os.path.join(my_Nw_buf_path, f'Hw_buffeting_{i}.json')
        with open(Nw_path, 'r') as f:
            std_delta_local['Nw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)
        with open(Hw_path, 'r') as f:
            std_delta_local['Hw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)


    dof_lst = ['x', 'y', 'z', 'rx', 'ry', 'rz']
    my_table = pd.DataFrame(columns=['Name', 'Mean', 'STD', 'Min', 'Max'])
    my_table2 = pd.DataFrame(columns=['Analysis', 'Type', 'DOF', 'Avg.', 'Min', 'P1', 'P10', 'P50', 'P90', 'P95', 'P99', 'Max'])

    sw_str_dof = ["$|\Delta_x|_{max}$ $[m]$",
                  "$|\Delta_y|_{max}$ $[m]$",
                  "$|\Delta_z|_{max}$ $[m]$",
                  "$|\Delta_{rx}|_{max}$ $[\degree]$",
                  "$|\Delta_{ry}|_{max}$ $[\degree]$",
                  "$|\Delta_{rz}|_{max}$ $[\degree]$"]
    buf_str_dof = ["$\sigma_{x, max}$ $[m]$",
                   "$\sigma_{y, max}$ $[m]$",
                   "$\sigma_{z, max}$ $[m]$",
                   "$\sigma_{rx, max}$ $[\degree]$",
                   "$\sigma_{ry, max}$ $[\degree]$",
                   "$\sigma_{rz, max}$ $[\degree]$"]
    ratio_sw_str_dof = ["Response ratio: $|\Delta_x|_{max}^I$ / $|\Delta_x|_{max}^H$",
                        "Response ratio: $|\Delta_y|_{max}^I$ / $|\Delta_y|_{max}^H$",
                        "Response ratio: $|\Delta_z|_{max}^I$ / $|\Delta_z|_{max}^H$",
                        "Response ratio: $|\Delta_{rx}|_{max}^I$ / $|\Delta_{rx}|_{max}^H$",
                        "Response ratio: $|\Delta_{ry}|_{max}^I$ / $|\Delta_{ry}|_{max}^H$",
                        "Response ratio: $|\Delta_{rz}|_{max}^I$ / $|\Delta_{rz}|_{max}^H$"]
    ratio_buf_str_dof = ["Response ratio: $\sigma_{x, max}^I$ / $\sigma_{x, max}^H$",
                         "Response ratio: $\sigma_{y, max}^I$ / $\sigma_{y, max}^H$",
                         "Response ratio: $\sigma_{z, max}^I$ / $\sigma_{z, max}^H$",
                         "Response ratio: $\sigma_{rx, max}^I$ / $\sigma_{rx, max}^H$",
                         "Response ratio: $\sigma_{ry, max}^I$ / $\sigma_{ry, max}^H$",
                         "Response ratio: $\sigma_{rz, max}^I$ / $\sigma_{rz, max}^H$"]
    for dof in [1, 2, 3]:
        # TABLE 1
        # Static wind
        sw_Nw_max_D_loc = np.array([func(np.max(np.abs(Nw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(n_Nw_sw_cases)])
        sw_Hw_max_D_loc = np.array([func(np.max(np.abs(Hw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(n_Nw_sw_cases)])
        sw_Nw_Hw_ratio_max_D_loc = sw_Nw_max_D_loc / sw_Hw_max_D_loc
        # my_table = my_table.append({'Name': f'Sw_Nw_{dof_lst[dof]}', 'Mean': str(np.mean(sw_Nw_max_D_loc)), 'STD': str(np.std(sw_Nw_max_D_loc)), 'Min': str(np.min(sw_Nw_max_D_loc)), 'Max': str(np.max(sw_Nw_max_D_loc))}, ignore_index=True)
        # my_table = my_table.append({'Name': f'Sw_Hw_{dof_lst[dof]}', 'Mean': str(np.mean(sw_Hw_max_D_loc)), 'STD': str(np.std(sw_Hw_max_D_loc)), 'Min': str(np.min(sw_Hw_max_D_loc)), 'Max': str(np.max(sw_Hw_max_D_loc))}, ignore_index=True)
        # my_table = my_table.append({'Name': f'Sw_NwByHw_{dof_lst[dof]}', 'Mean': str(np.mean(sw_Nw_Hw_ratio_max_D_loc)), 'STD': str(np.std(sw_Nw_Hw_ratio_max_D_loc)), 'Min': str(np.min(sw_Nw_Hw_ratio_max_D_loc)),'Max': str(np.max(sw_Nw_Hw_ratio_max_D_loc))}, ignore_index=True)
        # Buffeting
        buf_Nw_max_D_loc = np.array([func(np.max(np.abs(std_delta_local['Nw'][case][:n_g_nodes, dof])), dof) for case in range(n_Nw_sw_cases)])
        buf_Hw_max_D_loc = np.array([func(np.max(np.abs(std_delta_local['Hw'][case][:n_g_nodes, dof])), dof) for case in range(n_Nw_sw_cases)])
        buf_Nw_Hw_ratio_max_D_loc = buf_Nw_max_D_loc / buf_Hw_max_D_loc
        # my_table = my_table.append({'Name': f'Buf_Nw_{dof_lst[dof]}', 'Mean': str(np.mean(buf_Nw_max_D_loc)), 'STD': str(np.std(buf_Nw_max_D_loc)), 'Min': str(np.min(buf_Nw_max_D_loc)), 'Max': str(np.max(buf_Nw_max_D_loc))}, ignore_index=True)
        # my_table = my_table.append({'Name': f'Buf_Hw_{dof_lst[dof]}', 'Mean': str(np.mean(buf_Hw_max_D_loc)), 'STD': str(np.std(buf_Hw_max_D_loc)), 'Min': str(np.min(buf_Hw_max_D_loc)), 'Max': str(np.max(buf_Hw_max_D_loc))}, ignore_index=True)
        # my_table = my_table.append({'Name': f'Buf_NwByHw_{dof_lst[dof]}', 'Mean': str(np.mean(buf_Nw_Hw_ratio_max_D_loc)), 'STD': str(np.std(buf_Nw_Hw_ratio_max_D_loc)), 'Min': str(np.min(buf_Nw_Hw_ratio_max_D_loc)),'Max': str(np.max(buf_Nw_Hw_ratio_max_D_loc))}, ignore_index=True)
        # TABLE 2
        # Static wind
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), [ 'Static',      'Nw', f'{dof_lst[dof]}'] + [np.mean(          sw_Nw_max_D_loc)] + np.percentile(          sw_Nw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), [ 'Static',      'Hw', f'{dof_lst[dof]}'] + [np.mean(          sw_Hw_max_D_loc)] + np.percentile(          sw_Hw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), [ 'Static',   'Ratio', f'{dof_lst[dof]}'] + [np.mean( sw_Nw_Hw_ratio_max_D_loc)] + np.percentile( sw_Nw_Hw_ratio_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        # Buffeting
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), ['Buffeting',    'Nw', f'{dof_lst[dof]}'] + [np.mean(         buf_Nw_max_D_loc)] + np.percentile(         buf_Nw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), ['Buffeting',    'Hw', f'{dof_lst[dof]}'] + [np.mean(         buf_Hw_max_D_loc)] + np.percentile(         buf_Hw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), ['Buffeting', 'Ratio', f'{dof_lst[dof]}'] + [np.mean(buf_Nw_Hw_ratio_max_D_loc)] + np.percentile(buf_Nw_Hw_ratio_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)

        # "Versus" plots
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        min_D = np.min([sw_Hw_max_D_loc, sw_Nw_max_D_loc])
        max_D = np.max([sw_Hw_max_D_loc, sw_Nw_max_D_loc])
        plt.plot([min_D, max_D], [min_D, max_D], c='grey', alpha=0.5)
        plt.scatter(sw_Hw_max_D_loc, sw_Nw_max_D_loc, s=30, alpha=0.5, c='tab:brown', edgecolors='none')
        plt.ylabel(f'Inhomog. wind response: {sw_str_dof[dof]}')
        plt.xlabel(f'Equiv. homog. wind response: {sw_str_dof[dof]}')
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\sw_Versus_plots_dof_{dof}.png')
        plt.show()
        min_D = np.min([buf_Hw_max_D_loc, buf_Nw_max_D_loc])
        max_D = np.max([buf_Hw_max_D_loc, buf_Nw_max_D_loc])
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        plt.plot([min_D, max_D], [min_D, max_D], c='grey', alpha=0.5)
        plt.scatter(buf_Hw_max_D_loc, buf_Nw_max_D_loc, s=30, alpha=0.5, c='tab:brown', edgecolors='none')
        plt.ylabel(f'Inhomog. wind response: {buf_str_dof[dof]}')
        plt.xlabel(f'Equiv. homog. wind response: {buf_str_dof[dof]}')
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\buf_Versus_plots_dof_{dof}.png')
        plt.show()

        # (NOT) QQ plots
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        min_D = np.min([sw_Hw_max_D_loc, sw_Nw_max_D_loc])
        max_D = np.max([sw_Hw_max_D_loc, sw_Nw_max_D_loc])
        plt.plot([min_D, max_D], [min_D, max_D], c='grey', alpha=0.5)
        plt.scatter(np.sort(sw_Hw_max_D_loc), np.sort(sw_Nw_max_D_loc), s=30, alpha=0.5, c='tab:brown', edgecolors='none')
        plt.ylabel(f'Inhomog. wind response: {sw_str_dof[dof]}')
        plt.xlabel(f'Equiv. homog. wind response: {sw_str_dof[dof]}')
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\sw_QQ_plots_dof_{dof}.png')
        plt.show()
        min_D = np.min([buf_Hw_max_D_loc, buf_Nw_max_D_loc])
        max_D = np.max([buf_Hw_max_D_loc, buf_Nw_max_D_loc])
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        plt.plot([min_D, max_D], [min_D, max_D], c='grey', alpha=0.5)
        plt.scatter(np.sort(buf_Hw_max_D_loc), np.sort(buf_Nw_max_D_loc), s=30, alpha=0.5, c='tab:brown', edgecolors='none')
        plt.ylabel(f'Inhomog. wind response: {buf_str_dof[dof]}')
        plt.xlabel(f'Equiv. homog. wind response: {buf_str_dof[dof]}')
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\buf_QQ_plots_dof_{dof}.png')
        plt.show()

        def find_nearest(array, value):
            array = np.asarray(array)
            idx = (np.abs(array - value)).argmin()
            return array[idx]

        # Probability plots
        fig, ax1 = plt.subplots(dpi=400, figsize=(6.4, 5.3))
        ax2 = ax1.twiny()
        ymax_of_ratio_one = (np.arange(n_Nw_sw_cases)/n_Nw_sw_cases)[np.where(find_nearest(np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc), 1) == np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc))[0][0]]
        ax1.axvline(x=1, ymax=ymax_of_ratio_one, color='tab:brown', alpha=0.4, lw=2.5, ls='--', zorder=-1)
        ax2.scatter(np.sort(sw_Nw_max_D_loc), np.arange(n_Nw_sw_cases)/n_Nw_sw_cases, s=20, alpha=0.4, c='orange', edgecolors='none', label='Inhomog. response CDF')
        ax2.scatter(np.sort(sw_Hw_max_D_loc), np.arange(n_Nw_sw_cases)/n_Nw_sw_cases, s=20, alpha=0.4, c='blue',   edgecolors='none', label='Homog. response CDF')
        ax1.set_ylabel(f'Cumulative Distribution Function (CDF)')
        ax2.set_xlabel(f'Response: {sw_str_dof[dof]}')
        ax1.plot(np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc), np.arange(n_Nw_sw_cases)/n_Nw_sw_cases, alpha=0.6, lw=3, c='tab:brown', label='Response ratio CDF')
        # Plotting P50 and P90:
        ax1.axvline(x=np.percentile(np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc), 50), ymax=mapRange(0.5, ax1.get_ylim(),  [0 ,1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.axhline(y=0.5, xmax=mapRange(np.percentile(np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc), 50), ax1.get_xlim(),  [0, 1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.axvline(x=np.percentile(np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc), 95), ymax=mapRange(0.95, ax1.get_ylim(), [0 ,1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.axhline(y=0.95, xmax=mapRange(np.percentile(np.sort(sw_Nw_max_D_loc/sw_Hw_max_D_loc), 95), ax1.get_xlim(), [0, 1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.annotate('P95', xy=(mapRange(0.02, [0,1], ax1.get_xlim()), 0.96), color='tab:brown')
        ax1.annotate('P50', xy=(mapRange(0.02, [0,1], ax1.get_xlim()), 0.51), color='tab:brown')
        ax1.set_xlabel(f'{ratio_sw_str_dof[dof]}')
        handles1, labels1 = ax1.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        # fig.legend(handles2+handles1, labels2+labels1, loc=4, bbox_to_anchor=(.97, .15))
        ax2.grid(linestyle='-.', alpha=0.4)
        ax1.grid(linestyle='--', alpha=0.5)
        ax1.spines['bottom'].set_color('tab:brown')
        ax1.xaxis.label.set_color('tab:brown')
        ax1.tick_params(axis='x', colors='tab:brown')
        plt.tight_layout()
        plt.savefig(rf'results\sw_Prob_plots_dof_{dof}.png')
        plt.show()
        fig, ax1 = plt.subplots(dpi=400, figsize=(6.4, 5.3))
        ax2 = ax1.twiny()
        ymax_of_ratio_one = (np.arange(n_Nw_buf_cases)/n_Nw_buf_cases)[np.where(find_nearest(np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc), 1) == np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc))[0][0]]
        ax1.axvline(x=1, ymax=ymax_of_ratio_one, color='tab:brown', alpha=0.4, lw=2.5, ls='--', zorder=-1)
        ax2.scatter(np.sort(buf_Nw_max_D_loc), np.arange(n_Nw_buf_cases)/n_Nw_buf_cases, s=20, alpha=0.4, c='orange', edgecolors='none', label='Inhomog. response CDF')
        ax2.scatter(np.sort(buf_Hw_max_D_loc), np.arange(n_Nw_buf_cases)/n_Nw_buf_cases, s=20, alpha=0.4, c='blue',   edgecolors='none', label='Homog. response CDF')
        ax1.set_ylabel(f'Cumulative Distribution Function (CDF)')
        ax2.set_xlabel(f'Response: {buf_str_dof[dof]}')
        ax1.plot(np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc), np.arange(n_Nw_buf_cases)/n_Nw_buf_cases, alpha=0.6, lw=3, c='tab:brown', label='Response ratio CDF')
        # Plotting P50 and P90:
        ax1.axvline(x=np.percentile(np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc), 50), ymax=mapRange(0.5, ax1.get_ylim(),  [0 ,1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.axhline(y=0.5, xmax=mapRange(np.percentile(np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc), 50), ax1.get_xlim(),  [0, 1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.axvline(x=np.percentile(np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc), 95), ymax=mapRange(0.95, ax1.get_ylim(), [0 ,1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.axhline(y=0.95, xmax=mapRange(np.percentile(np.sort(buf_Nw_max_D_loc/buf_Hw_max_D_loc), 95), ax1.get_xlim(), [0, 1]), color='tab:brown', alpha=0.3, ls='-', lw=2, zorder=-1)
        ax1.annotate('P95', xy=(mapRange(0.02, [0,1], ax1.get_xlim()), 0.96), color='tab:brown')
        ax1.annotate('P50', xy=(mapRange(0.02, [0,1], ax1.get_xlim()), 0.51), color='tab:brown')
        ax1.set_xlabel(f'{ratio_buf_str_dof[dof]}')
        handles1, labels1 = ax1.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        # fig.legend(handles2+handles1, labels2+labels1, loc=4, bbox_to_anchor=(.97, .15))
        ax2.grid(linestyle='-.', alpha=0.4)
        ax1.grid(linestyle='--', alpha=0.5)
        ax1.spines['bottom'].set_color('tab:brown')
        ax1.xaxis.label.set_color('tab:brown')
        ax1.tick_params(axis='x', colors='tab:brown')
        plt.tight_layout()
        plt.savefig(rf'results\buf_Prob_plots_dof_{dof}.png')
        plt.show()
        # plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.scatter(np.sort(buf_Nw_max_D_loc), np.arange(n_Nw_buf_cases)/n_Nw_buf_cases, s=20, alpha=0.4, c='orange', edgecolors='none', label='Inhomogeneous')
        # plt.scatter(np.sort(buf_Hw_max_D_loc), np.arange(n_Nw_buf_cases)/n_Nw_buf_cases, s=20, alpha=0.4, c='blue',   edgecolors='none', label='Homogeneous'  )
        # plt.ylabel(f'Cumulative Distribution Function (CDF)')
        # plt.xlabel(f'{buf_str_dof[dof]}')
        # plt.grid()
        # plt.legend(loc=4)
        # plt.tight_layout()
        # plt.savefig(rf'results\buf_Prob_plots_dof_{dof}.png')
        # plt.show()

    # my_table.to_csv(r'results\Static_and_buffeting_response_stats_MeanSTD.csv')
    my_table2.to_csv(r'results\Static_and_buffeting_response_stats_Percentiles.csv')

# Nw_tables()


def Nw_plots(folder_suffix='3D'):  # Plots for the inhomogeneous wind journal paper
    """Inhomogeneous wind static & buffeting response plots + Arrow plots of the most conditioning wind cases"""
    matplotlib.rcParams.update({'font.size': 14})  # In first versions of thesis it was 12, then was changed to 14.
    ######################################################################################################
    # STATIC WIND
    ######################################################################################################
    n_g_nodes = len(g_node_coor)
    n_p_nodes = len(p_node_coor)
    g_s_3D = g_s_3D_func(g_node_coor)
    x = np.round(g_s_3D)
    # Getting the Nw wind properties into the same df
    my_Nw_path = os.path.join(os.getcwd(), r'intermediate_results', f'static_wind_{folder_suffix}')
    n_Nw_sw_cases = len(os.listdir(my_Nw_path))
    Nw_dict_all, Nw_D_loc, Hw_D_loc, Nw_U_bar_RMS, Nw_U_bar, Hw_U_bar, Hw_U_bar_RMS, Nw_beta_0,  Hw_beta_0, Nw_Ii, Hw_Ii = [],[],[],[],[],[],[],[],[],[],[]  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(n_Nw_sw_cases):
        Nw_path = os.path.join(my_Nw_path, f'Nw_dict_{i}.json')
        with open(Nw_path, 'r') as f:
            Nw_dict_all.append(json.load(f))
            Nw_U_bar.append(np.array(Nw_dict_all[i]['Nw_U_bar']))
            Hw_U_bar.append(np.array(Nw_dict_all[i]['Hw_U_bar']))
            Nw_U_bar_RMS.append(np.sqrt(np.mean(np.array(Nw_dict_all[i]['Nw_U_bar'])**2)))
            Hw_U_bar_RMS.append(np.sqrt(np.mean(np.array(Nw_dict_all[i]['Hw_U_bar'])**2)))
            Nw_beta_0.append(np.array(Nw_dict_all[i]['Nw_beta_0']))
            Hw_beta_0.append(np.array(Nw_dict_all[i]['Hw_beta_0']))
            Nw_D_loc.append(np.array(Nw_dict_all[i]['Nw_D_loc']))
            Hw_D_loc.append(np.array(Nw_dict_all[i]['Hw_D_loc']))
            Nw_Ii.append(np.array(Nw_dict_all[i]['Nw_Ii']))
            Hw_Ii.append(np.array(Nw_dict_all[i]['Hw_Ii']))
    Nw_U_bar = np.array(Nw_U_bar)
    Hw_U_bar = np.array(Hw_U_bar)
    Nw_Ii = np.array(Nw_Ii)
    Hw_Ii = np.array(Hw_Ii)
    Nw_beta_DB = beta_DB_func(np.array(Nw_beta_0))
    Hw_beta_DB = beta_DB_func(np.array(Hw_beta_0))

    def func(x, dof):
        """converts results in radians to degrees, if dof is an angle"""
        if dof >= 3:
            return deg(x)
        else:
            return x

    ##################################
    # SINGLE CASE PLOT
    ##################################
    plt.figure(dpi=400, figsize=(6.4, 5.3))
    for dof in [1]:
        for case in [14]:
            label1, label2 = ('Inhomogeneous case', 'Homogeneous case')
            plt.plot(x, func(Nw_D_loc[case][:n_g_nodes, dof], dof), lw=2., alpha=0.9, c='orange', label=label1)
            plt.plot(x, func(Hw_D_loc[case][:n_g_nodes, dof], dof), lw=2., alpha=0.9, c='blue', label=label2)
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel("$\Delta_y$ $[m]$")
        plt.legend(loc='upper center', bbox_to_anchor=(0.45, -0.16), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\single_case_sw_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
    print('To plot the corresponding wind quiver plot, use the general quiver plots but change: figsize=(6.2,5); change font of both cbar.ax xlabels to fontsize=12; add prefix to file name: font11; and do: matplotlib.rcParams.update({"font.size": 12})')

    ratio_sw_str_dof = ["$|\Delta_x|_{max}^I$ / $|\Delta_x|_{max}^H$",
                        "$|\Delta_y|_{max}^I$ / $|\Delta_y|_{max}^H$",
                        "$|\Delta_z|_{max}^I$ / $|\Delta_z|_{max}^H$",
                        "$|\Delta_{rx}|_{max}^I$ / $|\Delta_{rx}|_{max}^H$",
                        "$|\Delta_{ry}|_{max}^I$ / $|\Delta_{ry}|_{max}^H$",
                        "$|\Delta_{rz}|_{max}^I$ / $|\Delta_{rz}|_{max}^H$"]
    ratio_buf_str_dof = ["$\sigma_{x, max}^I$ / $\sigma_{x, max}^H$",
                         "$\sigma_{y, max}^I$ / $\sigma_{y, max}^H$",
                         "$\sigma_{z, max}^I$ / $\sigma_{z, max}^H$",
                         "$\sigma_{rx, max}^I$ / $\sigma_{rx, max}^H$",
                         "$\sigma_{ry, max}^I$ / $\sigma_{ry, max}^H$",
                         "$\sigma_{rz, max}^I$ / $\sigma_{rz, max}^H$"]
    ##################################
    # ALL CASE PLOTS
    ##################################
    for dof in [1,2,3]:
        ##################################
        # LINE PLOTS
        ##################################
        str_dof = ["$\Delta_x$ $[m]$",
                   "$\Delta_y$ $[m]$",
                   "$\Delta_z$ $[m]$",
                   "$\Delta_{rx}$ $[\degree]$",
                   "$\Delta_{ry}$ $[\degree]$",
                   "$\Delta_{rz}$ $[\degree]$"]
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(n_Nw_sw_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            plt.plot(x, func(Nw_D_loc[case][:n_g_nodes, dof], dof), lw=1.2, alpha=0.25, c='orange', label=label1)
            plt.plot(x, func(Hw_D_loc[case][:n_g_nodes, dof], dof), lw=1.2, alpha=0.25, c='blue', label=label2)
        plt.plot(x, func(np.max(np.array([Nw_D_loc[case][:n_g_nodes, dof] for case in range(n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='orange', lw=3, label=f'Inhomogeneous (envelope)')
        plt.plot(x, func(np.min(np.array([Nw_D_loc[case][:n_g_nodes, dof] for case in range(n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='orange', lw=3)
        plt.plot(x, func(np.max(np.array([Hw_D_loc[case][:n_g_nodes, dof] for case in range(n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='blue', lw=3, label=f'Homogeneous (envelope)')
        plt.plot(x, func(np.min(np.array([Hw_D_loc[case][:n_g_nodes, dof] for case in range(n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='blue', lw=3)
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\sw_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ##################################
        # SCATTER PLOTS
        ##################################
        str_dof = ["$|\Delta_x|_{max}$ $[m]$",
                   "$|\Delta_y|_{max}$ $[m]$",
                   "$|\Delta_z|_{max}$ $[m]$",
                   "$|\Delta_{rx}|_{max}$ $[\degree]$",
                   "$|\Delta_{ry}|_{max}$ $[\degree]$",
                   "$|\Delta_{rz}|_{max}$ $[\degree]$"]
        my_down_arrow = np.array([[-90.0000,   5.8488],
                                  [  0.0000, -86.5902],
                                  [ 90.0000,   5.8488],
                                  [ 30.0000,   5.8488],
                                  [ 30.0000,  83.4098],
                                  [-30.0000,  83.4098],
                                  [-30.0000,   5.8488]])  # draw polyline in AUTOCAD and do LIST command (use REGION, MASSPROP and MOVE to get it centered at C.O.G)
        my_up_arrow = np.array([[-90.0000, -5.8488],
                                [0.0000, 86.5902],
                                [90.0000, -5.8488],
                                [30.0000, -5.8488],
                                [30.0000, -83.4098],
                                [-30.0000, -83.4098],
                                [-30.0000, -5.8488]])  # obtained from AutoCAD, drawing a polyline and LIST command (use region and MASSPROP to get C.O.G)
        ########## w.r.t. U ##########
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(n_Nw_sw_cases): # n_Nw_sw_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None, None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(Hw_U_bar[case,0], func(np.max(np.abs(Nw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow, s=60, alpha=0.5, c='orange', edgecolors='none', label=label1)
            plt.scatter(Hw_U_bar[case,0], func(np.max(np.abs(Hw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow, s=60, alpha=0.5, c='blue'  , edgecolors='none', label=label2)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\sw_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ### ratio PLOT ###
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(n_Nw_sw_cases): # n_Nw_sw_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None, None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(Hw_U_bar[case,0], func(np.max(np.abs(Nw_D_loc[case][:n_g_nodes, dof])), dof) / func(np.max(np.abs(Hw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow, s=60, alpha=0.5, c='tab:brown', edgecolors='none', label=label1)
        plt.axhline(y=1.0, color='black', alpha=0.5, linestyle='-', zorder=0.1)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(ratio_sw_str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(rf'results\sw_ratio_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ########## w.r.t. BETA ##########
        fig = plt.figure(dpi=400, figsize=(6.4, 5.3))
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(n_Nw_sw_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None, None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            # arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            # arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(Nw_D_loc[case][:n_g_nodes, dof])), dof), marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='orange', edgecolors='none', label=label1)
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(Hw_D_loc[case][:n_g_nodes, dof])), dof), marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='blue'  , edgecolors='none', label=label2)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        # plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.54,0.115), rotation=23)
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=20)  # use without legend
        # plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.58, 0.89))
        plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.075), ncol=2)  # use with polar plot
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)  # use with rectangular plot
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(rf'results\sw_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ### ratio PLOT ###
        fig = plt.figure(dpi=400, figsize=(6.4, 5.3))
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(n_Nw_sw_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None, None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(Nw_D_loc[case][:n_g_nodes, dof])), dof) / func(np.max(np.abs(Hw_D_loc[case][:n_g_nodes, dof])), dof), marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='tab:brown', edgecolors='none', label=label1)
        plt.plot(np.linspace(0,2*np.pi,360), np.ones(360), color='black', alpha=0.5, linestyle='-', zorder=0.1)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=20)  # use without legend
        plt.annotate(ratio_sw_str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(rf'results\sw_ratio_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()

    ######################################################################################################
    # BUFFETING
    ######################################################################################################
    # Getting the Nw wind properties into the same df
    my_Nw_buf_path = os.path.join(os.getcwd(), r'intermediate_results', f'buffeting_{folder_suffix}')
    n_Nw_buf_cases = np.max([int(''.join(i for i in f if i.isdigit())) for f in os.listdir(my_Nw_buf_path)]) + 1  # use +1 to count for the 0.
    std_delta_local = {'Nw':np.nan*np.zeros((n_Nw_buf_cases, n_g_nodes, 6)),
                       'Hw':np.nan*np.zeros((n_Nw_buf_cases, n_g_nodes, 6)),}  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(n_Nw_buf_cases):
        Nw_path = os.path.join(my_Nw_buf_path, f'Nw_buffeting_{i}.json')
        Hw_path = os.path.join(my_Nw_buf_path, f'Hw_buffeting_{i}.json')
        with open(Nw_path, 'r') as f:
            std_delta_local['Nw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)
        with open(Hw_path, 'r') as f:
            std_delta_local['Hw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)

    ##################################
    # SINGLE CASE PLOT
    ##################################
    plt.figure(dpi=400, figsize=(6.4, 5.3))
    for dof in [2]:
        for case in [62]:
            label1, label2 = ('Inhomogeneous case', 'Homogeneous case')
            plt.plot(x, func(std_delta_local['Nw'][case,:, dof], dof), lw=2., alpha=0.9, c='orange', label=label1)
            plt.plot(x, func(std_delta_local['Hw'][case,:, dof], dof), lw=2., alpha=0.9, c='blue', label=label2)
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel("$\sigma_z$ $[m]$")
        plt.legend(loc='upper center', bbox_to_anchor=(0.45, -0.16), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\single_case_buf_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
    print('To plot the corresponding wind quiver plot, use the general quiver plots but change: figsize=(6.2,5); change font of both cbar.ax xlabels to fontsize=12; add prefix to file name: font11; and do: matplotlib.rcParams.update({"font.size": 12})')

    ##################################
    # ALL CASE PLOTS
    ##################################
    for dof in [1,2,3]:
        ##################################
        # LINE PLOTS
        ##################################
        str_dof = ["$\sigma_x$ $[m]$",
                   "$\sigma_y$ $[m]$",
                   "$\sigma_z$ $[m]$",
                   "$\sigma_{rx}$ $[\degree]$",
                   "$\sigma_{ry}$ $[\degree]$",
                   "$\sigma_{rz}$ $[\degree]$"]
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(n_Nw_buf_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            plt.plot(x, func(std_delta_local['Nw'][case,:, dof], dof), lw=1.2, alpha=0.25, c='orange', label=label1)
            plt.plot(x, func(std_delta_local['Hw'][case,:, dof], dof), lw=1.2, alpha=0.25, c='blue', label=label2)
        plt.plot(x, func(np.max(np.array([std_delta_local['Nw'][case,:, dof] for case in range(n_Nw_buf_cases)]), axis=0), dof), alpha=0.7, c='orange', lw=3, label=f'Inhomogeneous (max.)')
        plt.plot(x, func(np.max(np.array([std_delta_local['Hw'][case,:, dof] for case in range(n_Nw_buf_cases)]), axis=0), dof), alpha=0.7, c='blue', lw=3, label=f'Homogeneous (max.)')
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\buf_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ##################################
        # SCATTER PLOTS (from intermediate results)
        ##################################
        str_dof = ["$\sigma_{x, max}$ $[m]$",
                   "$\sigma_{y, max}$ $[m]$",
                   "$\sigma_{z, max}$ $[m]$",
                   "$\sigma_{rx, max}$ $[\degree]$",
                   "$\sigma_{ry, max}$ $[\degree]$",
                   "$\sigma_{rz, max}$ $[\degree]$"]
        ########## w.r.t. U ##########
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(n_Nw_buf_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(Hw_U_bar[case,0], func(np.max(np.abs(std_delta_local['Nw'][case,:, dof])), dof), marker=arrow, s=60, alpha=0.5, c='orange', edgecolors='none', label=label1)
            plt.scatter(Hw_U_bar[case,0], func(np.max(np.abs(std_delta_local['Hw'][case,:, dof])), dof), marker=arrow, s=60, alpha=0.5, c='blue'  , edgecolors='none', label=label2)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\buf_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ### ratio PLOT ###
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        for case in range(n_Nw_buf_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(Hw_U_bar[case,0], func(np.max(np.abs(std_delta_local['Nw'][case,:, dof])), dof)/func(np.max(np.abs(std_delta_local['Hw'][case,:, dof])), dof), marker=arrow, s=60, alpha=0.5, c='tab:brown', edgecolors='none', label=label1)
        plt.axhline(y=1.0, color='black', alpha=0.5, linestyle='-', zorder=0.1)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(ratio_buf_str_dof[dof])
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(rf'results\buf_ratio_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()

        ########## w.r.t. BETA ##########
        fig = plt.figure(dpi=400, figsize=(6.4, 5.3))
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plt.title(f'Buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(n_Nw_buf_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(std_delta_local['Nw'][case,:, dof])), dof), marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='orange', edgecolors='none', label=label1)
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(std_delta_local['Hw'][case,:, dof])), dof), marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='blue'  , edgecolors='none', label=label2)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        # plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.54,0.115), rotation=23)
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=20)  # use without legend
        # plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.58, 0.89))
        plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.075), ncol=2)  # use with polar plot
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(rf'results\buf_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ### ratio PLOT ###
        fig = plt.figure(dpi=400, figsize=(6.4, 5.3))
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        for case in range(n_Nw_buf_cases):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(std_delta_local['Nw'][case,:, dof])), dof)/func(np.max(np.abs(std_delta_local['Hw'][case,:, dof])), dof), marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='tab:brown', edgecolors='none', label=label1)
        plt.plot(np.linspace(0,2*np.pi,360), np.ones(360), color='black', alpha=0.5, linestyle='-', zorder=0.1)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=20)  # use without legend
        plt.annotate(ratio_buf_str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(rf'results\buf_ratio_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()

    ######################################################################################################
    # STATIC WIND + BUFFETING
    ######################################################################################################
    kp = 3.5  # peak factor

    Nw_sw_plus_buf =  np.array([np.array([func(Nw_D_loc[case][:n_g_nodes, dof], dof) + kp * func(std_delta_local['Nw'][case, :, dof], dof) for dof in range(6)]).T for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases))]) # shape (n_cases, n_g_nodes, n_dof)
    Nw_sw_minus_buf = np.array([np.array([func(Nw_D_loc[case][:n_g_nodes, dof], dof) - kp * func(std_delta_local['Nw'][case, :, dof], dof) for dof in range(6)]).T for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases))]) # shape (n_cases, n_g_nodes, n_dof)
    Hw_sw_plus_buf =  np.array([np.array([func(Hw_D_loc[case][:n_g_nodes, dof], dof) + kp * func(std_delta_local['Hw'][case, :, dof], dof) for dof in range(6)]).T for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases))]) # shape (n_cases, n_g_nodes, n_dof)
    Hw_sw_minus_buf = np.array([np.array([func(Hw_D_loc[case][:n_g_nodes, dof], dof) - kp * func(std_delta_local['Hw'][case, :, dof], dof) for dof in range(6)]).T for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases))]) # shape (n_cases, n_g_nodes, n_dof)
    Nw_sw_plus_buf_absmax = np.max(np.max(np.array([np.abs(Nw_sw_plus_buf), np.abs(Nw_sw_minus_buf)]), axis=0), axis=1)  # Final shape (n_cases, n_dof). First max is along both arrays, second max is along n_g_nodes
    Hw_sw_plus_buf_absmax = np.max(np.max(np.array([np.abs(Hw_sw_plus_buf), np.abs(Hw_sw_minus_buf)]), axis=0), axis=1)  # Final shape (n_cases, n_dof). First max is along both arrays, second max is along n_g_nodes

    for dof in [1, 2, 3]:
        ##################################
        # LINE PLOTS
        ##################################
        str_dof = [r"$\Delta_x\/\pm\/k_p\times\sigma_x $ $[m]$",
                   r"$\Delta_y\/\pm\/k_p\times\sigma_y $ $[m]$",
                   r"$\Delta_z\/\pm\/k_p\times\sigma_z $ $[m]$",
                   r"$\Delta_{rx}\/\pm\/k_p\times\sigma_{rx} $ $[\degree]$",
                   r"$\Delta_{ry}\/\pm\/k_p\times\sigma_{ry} $ $[\degree]$",
                   r"$\Delta_{rz}\/\pm\/k_p\times\sigma_{rz} $ $[\degree]$"]
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Static + buffeting response ({n_Nw_buf_cases} worst 1h-events)')

        for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases)):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            plt.plot(x,  Nw_sw_plus_buf[case, :, dof], lw=1.2, alpha=0.25, c='orange', label=label1)
            plt.plot(x, Nw_sw_minus_buf[case, :, dof], lw=1.2, alpha=0.25, c='orange')
            plt.plot(x,  Hw_sw_plus_buf[case, :, dof], lw=1.2, alpha=0.25, c='blue', label=label2)
            plt.plot(x, Hw_sw_minus_buf[case, :, dof], lw=1.2, alpha=0.25, c='blue')
        plt.plot(x, np.max(Nw_sw_plus_buf[:,:,dof] , axis=0), alpha=0.7, c='orange', lw=3, label=f'Inhomogeneous (envelope)')
        plt.plot(x, np.min(Nw_sw_minus_buf[:,:,dof], axis=0), alpha=0.7, c='orange', lw=3)
        plt.plot(x, np.max(Hw_sw_plus_buf[:,:,dof] , axis=0), alpha=0.7, c='blue', lw=3, label=f'Homogeneous (envelope)')
        plt.plot(x, np.min(Hw_sw_minus_buf[:,:,dof], axis=0), alpha=0.7, c='blue', lw=3)
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\sw_buf_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ##################################
        # SCATTER PLOTS (from intermediate results)
        ##################################
        str_dof = [r"$|\Delta_x\/\pm\/k_p\times\sigma_x|_{max} $ $[m]$",
                   r"$|\Delta_y\/\pm\/k_p\times\sigma_y|_{max} $ $[m]$",
                   r"$|\Delta_z\/\pm\/k_p\times\sigma_z|_{max} $ $[m]$",
                   r"$|\Delta_{rx}\/\pm\/k_p\times\sigma_{rx}|_{max} $ $[\degree]$",
                   r"$|\Delta_{ry}\/\pm\/k_p\times\sigma_{ry}|_{max} $ $[\degree]$",
                   r"$|\Delta_{rz}\/\pm\/k_p\times\sigma_{rz}|_{max} $ $[\degree]$"]
        ########## w.r.t. U ##########
        plt.figure(dpi=400, figsize=(6.4, 5.3))
        # plt.title(f'Static + buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases)):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(Hw_U_bar[case,0], Nw_sw_plus_buf_absmax[case][dof], marker=arrow, s=60, alpha=0.5, c='orange', edgecolors='none', label=label1)
            plt.scatter(Hw_U_bar[case,0], Hw_sw_plus_buf_absmax[case][dof], marker=arrow, s=60, alpha=0.5, c='blue'  , edgecolors='none', label=label2)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\sw_buf_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ########## w.r.t. BETA ##########
        fig = plt.figure(dpi=400, figsize=(6.4, 5.3))
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plt.title(f'Static + buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(min(n_Nw_sw_cases, n_Nw_buf_cases)):
            label1, label2 = ('Inhomogeneous (all cases)', 'Homogeneous (all cases)') if case == 0 else (None,None)
            beta_DB_1_case = beta_DB_func(Hw_beta_0[case][0])
            plt.scatter(beta_DB_1_case, Nw_sw_plus_buf_absmax[case][dof], marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='orange', edgecolors='none', label=label1)
            plt.scatter(beta_DB_1_case, Hw_sw_plus_buf_absmax[case][dof], marker='o', s=Hw_U_bar[case,0]*4-np.min(Hw_U_bar[:,0])*4+4, alpha=0.5, c='blue'  , edgecolors='none', label=label2)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        # plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.54,0.115), rotation=23)  # use with legend
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=20)  # use without legend
        # plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.58, 0.89))   # use with legend
        plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.075), ncol=2)  # use with polar plot
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(rf'results\sw_buf_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()

    ######################################################################################################
    # SELECTED WIND PLOTS, WITH MOST IMPACT ON RESPONSE
    ######################################################################################################
    # WIND QUIVER PLOTS (U AND BETA DISTRIBUTIONS ALONG THE FJORD)
    ######################################################################################################
    matplotlib.rcParams.update({'font.size': 13})
    # Summarizing the important quantities
    Nw_sw_maxs = np.array([[func(np.max(np.abs(Nw_D_loc[case][:n_g_nodes, dof])), dof) for dof in range(6)] for case in range(n_Nw_sw_cases)])  # shape (n_cases, n_dof)
    Hw_sw_maxs = np.array([[func(np.max(np.abs(Hw_D_loc[case][:n_g_nodes, dof])), dof) for dof in range(6)] for case in range(n_Nw_sw_cases)])  # shape (n_cases, n_dof)
    Nw_buf_maxs = np.array([[func(np.max(np.abs(std_delta_local['Nw'][case, :, dof])), dof) for dof in range(6)] for case in range(n_Nw_buf_cases)])  # shape (n_cases, n_dof)
    Hw_buf_maxs = np.array([[func(np.max(np.abs(std_delta_local['Hw'][case, :, dof])), dof) for dof in range(6)] for case in range(n_Nw_buf_cases)])  # shape (n_cases, n_dof)
    Nw_sw_plus_buf_absmax = Nw_sw_plus_buf_absmax
    Hw_sw_plus_buf_absmax = Hw_sw_plus_buf_absmax
    # Getting the indexes of the sorted data by response magnitude, in descending order, separately for each dof
    Nw_sw_maxs_argsorts = np.array([Nw_sw_maxs[:,dof].argsort()[::-1] for dof in range(6)]).T
    Hw_sw_maxs_argsorts = np.array([Hw_sw_maxs[:,dof].argsort()[::-1] for dof in range(6)]).T
    Nw_buf_maxs_argsorts = np.array([Nw_buf_maxs[:,dof].argsort()[::-1] for dof in range(6)]).T
    Hw_buf_maxs_argsorts = np.array([Hw_buf_maxs[:,dof].argsort()[::-1] for dof in range(6)]).T
    Nw_sw_buf_maxs_argsorts = np.array([Nw_sw_plus_buf_absmax[:,dof].argsort()[::-1] for dof in range(6)]).T
    Hw_sw_buf_maxs_argsorts = np.array([Hw_sw_plus_buf_absmax[:,dof].argsort()[::-1] for dof in range(6)]).T
    Nw_all_argsorts = {'Nw':{'sw':Nw_sw_maxs_argsorts,
                             'buf':Nw_buf_maxs_argsorts,
                             'sw_buf':Nw_sw_buf_maxs_argsorts},
                       'Hw': {'sw': Hw_sw_maxs_argsorts,
                              'buf': Hw_buf_maxs_argsorts,
                              'sw_buf': Hw_sw_buf_maxs_argsorts}}
    ######################################################################################################
    lats_bridge, lons_bridge = bridge_WRF_nodes_coor_func(n_bridge_WRF_nodes=n_g_nodes).T

    ordinal = lambda n: "%d%s" % (n, "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])  # just a function to convert int to an ordinal string. e.g. 1->'1st'

    def interpolate_from_n_nodes_to_nearest_n_nodes_plotted(arr_to_interp, n_plot_nodes):
        """Example: from U_bar with size (n_g_nodes), it returns U_bar with size (n_nodes_plotted). It selects equally spaced indexes of arr_to_interp"""
        n_arr_nodes = len(arr_to_interp)
        n_arr_elems = n_arr_nodes - 1
        n_plot_elems = n_plot_nodes - 1
        assert n_plot_elems in sympy.divisors(n_arr_elems)
        idxs_to_plot = np.round(np.linspace(0, n_arr_nodes-1, n_plot_nodes)).astype(int)
        return arr_to_interp[idxs_to_plot]

    n_plot_nodes = 11  # number of nodes to plot along the bridge

    for analysis_type in ['sw', 'buf']:  # , 'sw_buf']:
        for rank_to_plot in range(0,5):  # 0 returns the 1st Nw wind case that gives the highest response in dof. 1 gives the 2nd case, and so on...
            for dof in [1,2,3]:
                str_dof = {'sw':["$|\Delta_x|_{max}$",
                                 "$|\Delta_y|_{max}$",
                                 "$|\Delta_z|_{max}$",
                                 "$|\Delta_{rx}|_{max}$",
                                 "$|\Delta_{ry}|_{max}$",
                                 "$|\Delta_{rz}|_{max}$"],
                          'buf':["$\sigma_{x, max}$",
                                 "$\sigma_{y, max}$",
                                 "$\sigma_{z, max}$",
                                 "$\sigma_{rx, max}$",
                                 "$\sigma_{ry, max}$",
                                 "$\sigma_{rz, max}$"],
                      'sw_buf':[r"$|\Delta_x\/\pm\/k_p\times\sigma_x|_{max}$",
                                r"$|\Delta_y\/\pm\/k_p\times\sigma_y|_{max}$",
                                r"$|\Delta_z\/\pm\/k_p\times\sigma_z|_{max}$",
                                r"$|\Delta_{rx}\/\pm\/k_p\times\sigma_{rx}|_{max}$",
                                r"$|\Delta_{ry}\/\pm\/k_p\times\sigma_{ry}|_{max}$",
                                r"$|\Delta_{rz}\/\pm\/k_p\times\sigma_{rz}|_{max}$"]}

                def truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
                    new_cmap = colors.LinearSegmentedColormap.from_list(
                        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=minval, b=maxval),
                        cmap(np.linspace(minval, maxval, n)))
                    return new_cmap

                case_idx = Nw_all_argsorts['Nw'][analysis_type][rank_to_plot][dof]  # The rank_to_plot'th index of the Nw wind case that maximizes dof

                Nw_ws_to_plot = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Nw_U_bar[case_idx], n_plot_nodes)
                Nw_wd_to_plot = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Nw_beta_DB[case_idx], n_plot_nodes)
                Nw_Iu_to_plot = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Nw_Ii[case_idx,:,0], n_plot_nodes)
                Hw_ws_to_plot = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Hw_U_bar[case_idx], n_plot_nodes)
                Hw_wd_to_plot = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Hw_beta_DB[case_idx], n_plot_nodes)
                Hw_Iu_to_plot = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Hw_Ii[case_idx, :, 0], n_plot_nodes)
                Iu_min = np.min(Nw_Ii[:, :, 0])
                Iu_max = np.max(Nw_Ii[:, :, 0])
                lats_bridge = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(lats_bridge, n_plot_nodes)
                lons_bridge = interpolate_from_n_nodes_to_nearest_n_nodes_plotted(lons_bridge, n_plot_nodes)
                cm = truncate_colormap(matplotlib.cm.Blues, 0.1, 1.0)  # cividis_r
                norm = matplotlib.colors.Normalize()
                sm = matplotlib.cm.ScalarMappable(cmap=cm, norm=norm)
                cm2 = truncate_colormap(matplotlib.cm.Oranges, 0.1, 1.0)  # removing the first 10% out of the cmap, which were too bright/transparent
                norm2 = matplotlib.colors.Normalize(vmin=Iu_min, vmax=Iu_max)
                sm2 = matplotlib.cm.ScalarMappable(cmap=cm2, norm=norm2)
                # fig, axes = plt.subplots(ncols=4, sharex=True, sharey=True, dpi=400, gridspec_kw={'width_ratios': [10,10,2,2]})
                fig, axes = plt.subplots(1,2, sharex=True, sharey=True, dpi=400, constrained_layout=True, figsize=(6.35,5))  # use 6.2 during single event plot figure
                # ax1 = fig.add_subplot(1, 2, 1)  # for Nw wind
                # ax2 = fig.add_subplot(1, 2, 2, sharex=ax1, sharey=ax1)  # for Hw wind
                # ax3 = fig.add_subplot(1, 2, 3)  # for colorbar 1
                # ax4 = fig.add_subplot(1, 2, 4)  # for colorbar 2
                fig.add_gridspec()
                plt.xlim(5.355, 5.41)
                plt.ylim(60.077, 60.135)
                fig.suptitle(f'{ordinal(rank_to_plot+1)} inhomog. wind event that maximizes {str_dof[analysis_type][dof]}', y=0.995)
                title_list = [r'Inhomog. wind', r'Eqv. homog. wind'] #[r'Inhomog. wind $\it{U^I}$', r'Equiv. homog. wind $\it{U^H}$'] #   [r'Inhomog. wind $\it{\bf{U^I}}$', r'Equiv. homog. wind $\it{\bf{U^H}}$']
                axes[0].set_title(title_list[0])
                axes[1].set_title(title_list[1])
                axes[0].set_aspect(lat_lon_aspect_ratio, adjustable='box')
                axes[1].set_aspect(lat_lon_aspect_ratio, adjustable='box')
                axes[0].scatter(*np.array([lons_bridge, lats_bridge]), color=cm2(norm2(Nw_Iu_to_plot)), s=normalize(Nw_Iu_to_plot, old_bounds=[Iu_min, Iu_max], new_bounds=[15, 160]))
                axes[0].quiver(*np.array([lons_bridge, lats_bridge]), -Nw_ws_to_plot * np.sin(Nw_wd_to_plot), -Nw_ws_to_plot * np.cos(Nw_wd_to_plot), color=cm(norm(Nw_ws_to_plot)), angles='uv', scale=100, width=0.02, headlength=3, headaxislength=3)
                axes[1].scatter(*np.array([lons_bridge, lats_bridge]), color=cm2(norm2(Hw_Iu_to_plot)), s=normalize(Hw_Iu_to_plot, old_bounds=[Iu_min, Iu_max], new_bounds=[15, 160]))
                axes[1].quiver(*np.array([lons_bridge, lats_bridge]), -Hw_ws_to_plot * np.sin(Hw_wd_to_plot), -Hw_ws_to_plot * np.cos(Hw_wd_to_plot), color=cm(norm(Hw_ws_to_plot)), angles='uv', scale=100, width=0.02, headlength=3, headaxislength=3)
                cbar2 = fig.colorbar(sm2, cax=None, fraction=0.106, pad=0.056) #, format=matplotlib.ticker.FuncFormatter(matplotlib.ticker.FormatStrFormatter('%.2f')))  # play with these values until the colorbar has good size and the entire plot and axis labels is visible
                cbar2.ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(7))
                cbar2.ax.set_xlabel('         $I_u$', c=matplotlib.cm.Oranges(999999999999), fontsize=14)
                cbar2.ax.tick_params(labelcolor=matplotlib.cm.Oranges(999999999999))
                cbar = fig.colorbar(sm, cax=None, fraction=0.106, pad=0.056)  # play with these values until the colorbar has good size and the entire plot and axis labels is visible. Good values for 1 colorbar: fraction=0.078, pad=0.076. For 2 colorbars: fraction=0.097, pad=0.076
                cbar.ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%.1f'))
                cbar.ax.tick_params(labelcolor =matplotlib.cm.Blues(999999999999))
                cbar.ax.set_xlabel('         U [m/s]', c=matplotlib.cm.Blues(999999999999), fontsize=14)
                fig.supxlabel('    Longitude [$\degree$]', x=0.41, y=0.01)
                fig.supylabel('Latitude [$\degree$]')
                # fig.set_constrained_layout_pads(h_pad=0.25, wspace=0.05)
                plt.savefig(fr'plots/font10_U_{analysis_type}_Nw_vs_Hw_rank-{rank_to_plot}_dof-{dof}.png')
                plt.show()
                plt.close()
                # # MAKE AN EXCEL WITH ALL WRF CASES ORGANIZED, TO SEND TO THE CONSULTANTS AMC AND OON
                #
                # Nw_ws_all = np.array([interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Nw_U_bar[case_idx], n_plot_nodes) for case_idx in range(n_Nw_sw_cases)])
                # Nw_wd_all = np.array([interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Nw_beta_DB[case_idx], n_plot_nodes) for case_idx in range(n_Nw_sw_cases)])
                # Nw_Iu_all = np.array([interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Nw_Ii[case_idx,:,0], n_plot_nodes) for case_idx in range(n_Nw_sw_cases)])
                # Hw_ws_all = np.array([interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Hw_U_bar[case_idx], n_plot_nodes) for case_idx in range(n_Nw_sw_cases)])
                # Hw_wd_all = np.array([interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Hw_beta_DB[case_idx], n_plot_nodes) for case_idx in range(n_Nw_sw_cases)])
                # Hw_Iu_all = np.array([interpolate_from_n_nodes_to_nearest_n_nodes_plotted(Hw_Ii[case_idx, :, 0], n_plot_nodes) for case_idx in range(n_Nw_sw_cases)])

# Nw_plots()

def Nw_plots_for_EACWE22(add_box_plot=False):  # for European African Conference of Wind Engineering. THIS COMPARES COSINE RULE WITH 3D SKEW WIND WITH INHOMOGENEOUS 3D SKEW WIND
    """Inhomogeneous wind static & buffeting response plots + Arrow plots of the ost conditioning wind cases"""
    matplotlib.rcParams.update({'font.size': 13})
    ######################################################################################################
    # STATIC WIND
    ######################################################################################################
    n_g_nodes = len(g_node_coor)
    n_p_nodes = len(p_node_coor)
    g_s_3D = g_s_3D_func(g_node_coor)
    x = np.round(g_s_3D)
    # Getting the Nw wind properties into the same df
    C1_my_Nw_path = os.path.join(os.getcwd(), r'intermediate_results', 'static_wind_cos_rule')
    C2_my_Nw_path = os.path.join(os.getcwd(), r'intermediate_results', 'static_wind_3D')
    C1_n_Nw_sw_cases = len(os.listdir(C1_my_Nw_path))
    C2_n_Nw_sw_cases = len(os.listdir(C1_my_Nw_path))
    assert C1_n_Nw_sw_cases == C2_n_Nw_sw_cases
    C1_Nw_dict_all, C1_Nw_D_loc, C1_Hw_D_loc, C1_Nw_U_bar_RMS, C1_Nw_U_bar, C1_Hw_U_bar, C1_Hw_U_bar_RMS, C1_Nw_beta_0, C1_Hw_beta_0, C1_Nw_Ii, C1_Hw_Ii = [],[],[],[],[],[],[],[],[],[],[]  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    C2_Nw_dict_all, C2_Nw_D_loc, C2_Hw_D_loc, C2_Nw_U_bar_RMS, C2_Nw_U_bar, C2_Hw_U_bar, C2_Hw_U_bar_RMS, C2_Nw_beta_0, C2_Hw_beta_0, C2_Nw_Ii, C2_Hw_Ii = [], [], [], [], [], [], [], [], [], [], []  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(C1_n_Nw_sw_cases):
        Nw_path = os.path.join(C1_my_Nw_path, f'Nw_dict_{i}.json')
        with open(Nw_path, 'r') as f:
            C1_Nw_dict_all.append(json.load(f))
            C1_Nw_U_bar.append(np.array(C1_Nw_dict_all[i]['Nw_U_bar']))
            C1_Hw_U_bar.append(np.array(C1_Nw_dict_all[i]['Hw_U_bar']))
            C1_Nw_U_bar_RMS.append(np.sqrt(np.mean(np.array(C1_Nw_dict_all[i]['Nw_U_bar'])**2)))
            C1_Hw_U_bar_RMS.append(np.sqrt(np.mean(np.array(C1_Nw_dict_all[i]['Hw_U_bar'])**2)))
            C1_Nw_beta_0.append(np.array(C1_Nw_dict_all[i]['Nw_beta_0']))
            C1_Hw_beta_0.append(np.array(C1_Nw_dict_all[i]['Hw_beta_0']))
            C1_Nw_D_loc.append(np.array(C1_Nw_dict_all[i]['Nw_D_loc']))
            C1_Hw_D_loc.append(np.array(C1_Nw_dict_all[i]['Hw_D_loc']))
            C1_Nw_Ii.append(np.array(C1_Nw_dict_all[i]['Nw_Ii']))
            C1_Hw_Ii.append(np.array(C1_Nw_dict_all[i]['Hw_Ii']))
    C1_Nw_U_bar = np.array(C1_Nw_U_bar)
    C1_Hw_U_bar = np.array(C1_Hw_U_bar)
    C1_Nw_Ii = np.array(C1_Nw_Ii)
    C1_Hw_Ii = np.array(C1_Hw_Ii)
    C1_Nw_beta_DB = beta_DB_func(np.array(C1_Nw_beta_0))
    C1_Hw_beta_DB = beta_DB_func(np.array(C1_Hw_beta_0))
    for i in range(C2_n_Nw_sw_cases):
        Nw_path = os.path.join(C2_my_Nw_path, f'Nw_dict_{i}.json')
        with open(Nw_path, 'r') as f:
            C2_Nw_dict_all.append(json.load(f))
            C2_Nw_U_bar.append(np.array(C2_Nw_dict_all[i]['Nw_U_bar']))
            C2_Hw_U_bar.append(np.array(C2_Nw_dict_all[i]['Hw_U_bar']))
            C2_Nw_U_bar_RMS.append(np.sqrt(np.mean(np.array(C2_Nw_dict_all[i]['Nw_U_bar'])**2)))
            C2_Hw_U_bar_RMS.append(np.sqrt(np.mean(np.array(C2_Nw_dict_all[i]['Hw_U_bar'])**2)))
            C2_Nw_beta_0.append(np.array(C2_Nw_dict_all[i]['Nw_beta_0']))
            C2_Hw_beta_0.append(np.array(C2_Nw_dict_all[i]['Hw_beta_0']))
            C2_Nw_D_loc.append(np.array(C2_Nw_dict_all[i]['Nw_D_loc']))
            C2_Hw_D_loc.append(np.array(C2_Nw_dict_all[i]['Hw_D_loc']))
            C2_Nw_Ii.append(np.array(C2_Nw_dict_all[i]['Nw_Ii']))
            C2_Hw_Ii.append(np.array(C2_Nw_dict_all[i]['Hw_Ii']))
    C2_Nw_U_bar = np.array(C2_Nw_U_bar)
    C2_Hw_U_bar = np.array(C2_Hw_U_bar)
    C2_Nw_Ii = np.array(C2_Nw_Ii)
    C2_Hw_Ii = np.array(C2_Hw_Ii)
    C2_Nw_beta_DB = beta_DB_func(np.array(C2_Nw_beta_0))
    C2_Hw_beta_DB = beta_DB_func(np.array(C2_Hw_beta_0))

    def func(x, dof):
        """converts results in radians to degrees, if dof is an angle"""
        if dof >= 3:
            return deg(x)
        else:
            return x

    ##################################
    # SINGLE CASE PLOT
    ##################################
    str_dof = ["$\Delta_x$ $[m]$",
               "$\Delta_y$ $[m]$",
               "$\Delta_z$ $[m]$",
               "$\Delta_{rx}$ $[\degree]$",
               "$\Delta_{ry}$ $[\degree]$",
               "$\Delta_{rz}$ $[\degree]$"]

    plt.figure(dpi=400)
    for dof in [1,2,3]:
        for case in [0]:
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)')
            plt.plot(x, func(C1_Hw_D_loc[case][:n_g_nodes, dof], dof), lw=2., alpha=0.9, c='green', label=label1)
            plt.plot(x, func(C2_Hw_D_loc[case][:n_g_nodes, dof], dof), lw=2., alpha=0.9, c='blue', label=label2)
            plt.plot(x, func(C2_Nw_D_loc[case][:n_g_nodes, dof], dof), lw=2., alpha=0.9, c='orange', label=label3)
        plt.xlabel('x [m]  (position along the arc)')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\single_case_sw_lines_Nw_VS_Hw_case_{case}_dof_{dof}.png')
        plt.show()
    print('To plot the corresponding wind quiver plot, use the general quiver plots but change: figsize=(6.2,5); change font of both cbar.ax xlabels to fontsize=12; add prefix to file name: font11; and do: matplotlib.rcParams.update({"font.size": 12})')



    for dof in [1,2,3]:
        ##################################
        # LINE PLOTS
        ##################################
        str_dof = ["$\Delta_x$ $[m]$",
                   "$\Delta_y$ $[m]$",
                   "$\Delta_z$ $[m]$",
                   "$\Delta_{rx}$ $[\degree]$",
                   "$\Delta_{ry}$ $[\degree]$",
                   "$\Delta_{rz}$ $[\degree]$"]
        plt.figure(dpi=400)
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(C1_n_Nw_sw_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None,None,None)
            plt.plot(x, func(C1_Hw_D_loc[case][:n_g_nodes, dof], dof), lw=1.2, alpha=0.25, c='green', label=label1)
            plt.plot(x, func(C2_Hw_D_loc[case][:n_g_nodes, dof], dof), lw=1.2, alpha=0.25, c='blue', label=label2)
            plt.plot(x, func(C2_Nw_D_loc[case][:n_g_nodes, dof], dof), lw=1.2, alpha=0.25, c='orange', label=label3)
        plt.plot(x, func(np.max(np.array([C1_Hw_D_loc[case][:n_g_nodes, dof] for case in range(C1_n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='green', lw=3, label=f'Cos rule - Homog. (envelope)')
        plt.plot(x, func(np.min(np.array([C1_Hw_D_loc[case][:n_g_nodes, dof] for case in range(C1_n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='green', lw=3)
        plt.plot(x, func(np.max(np.array([C2_Hw_D_loc[case][:n_g_nodes, dof] for case in range(C2_n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='blue', lw=3, label=f'3D skew wind - Homog. (envelope)')
        plt.plot(x, func(np.min(np.array([C2_Hw_D_loc[case][:n_g_nodes, dof] for case in range(C2_n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='blue', lw=3)
        plt.plot(x, func(np.max(np.array([C2_Nw_D_loc[case][:n_g_nodes, dof] for case in range(C2_n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='orange', lw=3, label=f'3D skew wind - Inhomog. (envelope)')
        plt.plot(x, func(np.min(np.array([C2_Nw_D_loc[case][:n_g_nodes, dof] for case in range(C2_n_Nw_sw_cases)]), axis=0), dof), alpha=0.7, c='orange', lw=3)
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\C1VSC2_sw_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ##################################
        # SCATTER PLOTS
        ##################################
        str_dof = ["$|\Delta_x|_{max}$ $[m]$",
                   "$|\Delta_y|_{max}$ $[m]$",
                   "$|\Delta_z|_{max}$ $[m]$",
                   "$|\Delta_{rx}|_{max}$ $[\degree]$",
                   "$|\Delta_{ry}|_{max}$ $[\degree]$",
                   "$|\Delta_{rz}|_{max}$ $[\degree]$"]
        my_down_arrow = np.array([[-90.0000,   5.8488],
                                  [  0.0000, -86.5902],
                                  [ 90.0000,   5.8488],
                                  [ 30.0000,   5.8488],
                                  [ 30.0000,  83.4098],
                                  [-30.0000,  83.4098],
                                  [-30.0000,   5.8488]])  # draw polyline in AUTOCAD and do LIST command (use REGION, MASSPROP and MOVE to get it centered at C.O.G)
        ########## w.r.t. U ##########
        plt.figure(dpi=400)
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(C1_n_Nw_sw_cases): # n_Nw_sw_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            beta_DB_1_case = beta_DB_func(C1_Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(C1_Hw_U_bar[case,0], func(np.max(np.abs(C1_Hw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow, s=60, alpha=0.4, c='green', edgecolors='none', label=label1)
            plt.scatter(C2_Hw_U_bar[case,0], func(np.max(np.abs(C2_Hw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow, s=60, alpha=0.4, c='blue' , edgecolors='none', label=label2)
            plt.scatter(C2_Hw_U_bar[case,0], func(np.max(np.abs(C2_Nw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow, s=60, alpha=0.4, c='orange' , edgecolors='none', label=label3)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\C1VSC2_sw_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ########## w.r.t. BETA ##########
        fig = plt.figure(dpi=400)
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plt.title(f'Static wind response ({n_Nw_sw_cases} worst 1h-events)')
        for case in range(C1_n_Nw_sw_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            beta_DB_1_case = beta_DB_func(C1_Hw_beta_0[case][0])
            # arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            # arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(C1_Hw_D_loc[case][:n_g_nodes, dof])), dof), marker='o', s=C1_Hw_U_bar[case,0]*3-np.min(C1_Hw_U_bar[:,0])*3+3, alpha=0.4, c='green' , edgecolors='none', label=label2)
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(C2_Hw_D_loc[case][:n_g_nodes, dof])), dof), marker='o', s=C2_Hw_U_bar[case,0]*3-np.min(C2_Hw_U_bar[:,0])*3+3, alpha=0.4, c='blue'  , edgecolors='none', label=label1)
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(C2_Nw_D_loc[case][:n_g_nodes, dof])), dof), marker='o', s=C2_Nw_U_bar[case,0]*3-np.min(C2_Nw_U_bar[:,0])*3+3, alpha=0.4, c='orange', edgecolors='none', label=label2)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        # plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.54,0.115), rotation=23)
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=22)  # use without legend
        # plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.58, 0.89))
        plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.075), ncol=2)  # use with polar plot
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)  # use with rectangular plot
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(rf'results\C1VSC2_sw_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()

    ######################################################################################################
    # BUFFETING
    ######################################################################################################
    # Getting the Nw wind properties into the same df
    C1_my_Nw_buf_path = os.path.join(os.getcwd(), r'intermediate_results', 'buffeting_cos_rule')
    C2_my_Nw_buf_path = os.path.join(os.getcwd(), r'intermediate_results', 'buffeting_3D')
    C1_n_Nw_buf_cases = np.max([int(''.join(i for i in f if i.isdigit())) for f in os.listdir(C1_my_Nw_buf_path)]) + 1  # use +1 to count for the 0.
    C2_n_Nw_buf_cases = np.max([int(''.join(i for i in f if i.isdigit())) for f in os.listdir(C2_my_Nw_buf_path)]) + 1  # use +1 to count for the 0.
    assert C1_n_Nw_buf_cases == C2_n_Nw_buf_cases
    C1_std_delta_local = {'Nw':np.nan*np.zeros((C1_n_Nw_buf_cases, n_g_nodes, 6)),
                          'Hw':np.nan*np.zeros((C1_n_Nw_buf_cases, n_g_nodes, 6)),}  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(C1_n_Nw_buf_cases):
        Nw_path = os.path.join(C1_my_Nw_buf_path, f'Nw_buffeting_{i}.json')
        Hw_path = os.path.join(C1_my_Nw_buf_path, f'Hw_buffeting_{i}.json')
        with open(Nw_path, 'r') as f:
            C1_std_delta_local['Nw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)
        with open(Hw_path, 'r') as f:
            C1_std_delta_local['Hw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)
    C2_std_delta_local = {'Nw': np.nan * np.zeros((C2_n_Nw_buf_cases, n_g_nodes, 6)),
                          'Hw': np.nan * np.zeros((C2_n_Nw_buf_cases, n_g_nodes, 6)), }  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
    for i in range(C2_n_Nw_buf_cases):
        Nw_path = os.path.join(C2_my_Nw_buf_path, f'Nw_buffeting_{i}.json')
        Hw_path = os.path.join(C2_my_Nw_buf_path, f'Hw_buffeting_{i}.json')
        with open(Nw_path, 'r') as f:
            C2_std_delta_local['Nw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)
        with open(Hw_path, 'r') as f:
            C2_std_delta_local['Hw'][i] = np.array(json.load(f))  # shape (n_cases, n_g_nodes, n_dof)

    for dof in [1,2,3]:
        ##################################
        # LINE PLOTS
        ##################################
        str_dof = ["$\sigma_x$ $[m]$",
                   "$\sigma_y$ $[m]$",
                   "$\sigma_z$ $[m]$",
                   "$\sigma_{rx}$ $[\degree]$",
                   "$\sigma_{ry}$ $[\degree]$",
                   "$\sigma_{rz}$ $[\degree]$"]
        plt.figure(dpi=400)
        # plt.title(f'Buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(C1_n_Nw_buf_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            plt.plot(x, func(C1_std_delta_local['Hw'][case,:, dof], dof), lw=1.2, alpha=0.25, c='green' , label=label1)
            plt.plot(x, func(C2_std_delta_local['Hw'][case,:, dof], dof), lw=1.2, alpha=0.25, c='blue'  , label=label2)
            plt.plot(x, func(C2_std_delta_local['Nw'][case,:, dof], dof), lw=1.2, alpha=0.25, c='orange', label=label3)
        plt.plot(x, func(np.max(np.array([C1_std_delta_local['Hw'][case,:, dof] for case in range(C1_n_Nw_buf_cases)]), axis=0), dof), alpha=0.7, c='green' , lw=3, label=f'Cos rule - Homog. (max.)')
        plt.plot(x, func(np.max(np.array([C2_std_delta_local['Hw'][case,:, dof] for case in range(C2_n_Nw_buf_cases)]), axis=0), dof), alpha=0.7, c='blue'  , lw=3, label=f'3D skew wind - Homog. (max.)')
        plt.plot(x, func(np.max(np.array([C2_std_delta_local['Nw'][case,:, dof] for case in range(C2_n_Nw_buf_cases)]), axis=0), dof), alpha=0.7, c='orange', lw=3, label=f'3D skew wind - Inhomog. (max.)')
        plt.xlabel('x [m]  (Position along the arc)')
        plt.ylabel(str_dof[dof])
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\C1VSC2_buf_lines_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        ##################################
        # SCATTER PLOTS (from intermediate results)
        ##################################
        str_dof = ["$\sigma_{x, max}$ $[m]$",
                   "$\sigma_{y, max}$ $[m]$",
                   "$\sigma_{z, max}$ $[m]$",
                   "$\sigma_{rx, max}$ $[\degree]$",
                   "$\sigma_{ry, max}$ $[\degree]$",
                   "$\sigma_{rz, max}$ $[\degree]$"]
        ########## w.r.t. U ##########
        plt.figure(dpi=400)
        # plt.title(f'Buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(C1_n_Nw_buf_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            beta_DB_1_case = beta_DB_func(C1_Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            plt.scatter(C1_Hw_U_bar[case,0], func(np.max(np.abs(C1_std_delta_local['Hw'][case,:, dof])), dof), marker=arrow, s=60, alpha=0.4, c='green' , edgecolors='none', label=label1)
            plt.scatter(C2_Hw_U_bar[case,0], func(np.max(np.abs(C2_std_delta_local['Hw'][case,:, dof])), dof), marker=arrow, s=60, alpha=0.4, c='blue'  , edgecolors='none', label=label2)
            plt.scatter(C2_Hw_U_bar[case,0], func(np.max(np.abs(C2_std_delta_local['Nw'][case,:, dof])), dof), marker=arrow, s=60, alpha=0.4, c='orange', edgecolors='none', label=label3)
        plt.xlabel(r'$U^H$ [m/s]')
        plt.ylabel(str_dof[dof])
        h, l = plt.gca().get_legend_handles_labels()
        plt.grid()
        plt.tight_layout()
        plt.savefig(rf'results\C1VSC2_buf_scatt_wrtU_Nw_VS_Hw_dof_{dof}.png')
        plt.show()
        plt.figure(dpi=400, figsize=(12,0.8))
        plt.legend(h, l, loc='upper center', ncol=3)
        plt.axis('off')
        plt.savefig(rf'results\C1VSC2_buf_scatt_wrtU_Nw_VS_Hw_dof_{dof}_LEGEND.png')
        plt.show()
        ########## w.r.t. BETA ##########
        fig = plt.figure(dpi=400)
        ax = fig.add_subplot(111, projection='polar')
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        # plt.title(f'Buffeting response ({n_Nw_buf_cases} worst 1h-events)')
        for case in range(C1_n_Nw_buf_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            beta_DB_1_case = beta_DB_func(C1_Hw_beta_0[case][0])
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(C1_std_delta_local['Hw'][case,:, dof])), dof), marker='o', s=C1_Hw_U_bar[case,0]*3-np.min(C1_Hw_U_bar[:,0])*3+3, alpha=0.4, c='green' , edgecolors='none', label=label1)
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(C2_std_delta_local['Hw'][case,:, dof])), dof), marker='o', s=C1_Hw_U_bar[case,0]*3-np.min(C1_Hw_U_bar[:,0])*3+3, alpha=0.4, c='blue'  , edgecolors='none', label=label2)
            plt.scatter(beta_DB_1_case, func(np.max(np.abs(C2_std_delta_local['Nw'][case,:, dof])), dof), marker='o', s=C1_Nw_U_bar[case,0]*3-np.min(C1_Nw_U_bar[:,0])*3+3, alpha=0.4, c='orange', edgecolors='none', label=label3)
        # Plotting brigde axis
        bridge_node_angle, bridge_node_radius_norm = get_bridge_node_angles_and_radia_to_plot(ax)
        ax.plot(bridge_node_angle, bridge_node_radius_norm, linestyle='-', linewidth=3., alpha=0.4, color='black', marker="None", zorder=1.0)#,zorder=k+1)
        # plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.54,0.115), rotation=23)
        plt.annotate(r'$\beta^H_{Cardinal}$ [deg]', xycoords='figure fraction', xy=(0.555, 0.055), rotation=22)  # use without legend
        # plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.58, 0.89))
        plt.annotate(str_dof[dof], xycoords='figure fraction', xy=(0.585, 0.920))  # use without legend
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.075), ncol=2)  # use with polar plot
        # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(rf'results\C1VSC2_buf_scatt_wrtBeta_Nw_VS_Hw_dof_{dof}.png')
        plt.show()

        ##################################
        # SINGLE CASE PLOT
        ##################################
        str_dof = ["$\sigma_x$ $[m]$",
                   "$\sigma_y$ $[m]$",
                   "$\sigma_z$ $[m]$",
                   "$\sigma_{rx}$ $[\degree]$",
                   "$\sigma_{ry}$ $[\degree]$",
                   "$\sigma_{rz}$ $[\degree]$"]
        plt.figure(dpi=400)
        for dof in [1,2,3]:
            for case in [0]:
                label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)')
                plt.plot(x, func(C1_std_delta_local['Hw'][case, :, dof], dof), lw=2., alpha=0.9, c='green', label=label1)
                plt.plot(x, func(C2_std_delta_local['Hw'][case, :, dof], dof), lw=2., alpha=0.9, c='blue', label=label2)
                plt.plot(x, func(C2_std_delta_local['Nw'][case, :, dof], dof), lw=2., alpha=0.9, c='orange', label=label3)
            plt.xlabel('x [m]  (Position along the arc)')
            plt.ylabel(str_dof[dof])
            # plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
            plt.grid()
            plt.tight_layout()
            plt.savefig(rf'results\single_case_buf_lines_Nw_VS_Hw_case_{case}_dof_{dof}.png')
            plt.show()
        print('To plot the corresponding wind quiver plot, use the general quiver plots but change: figsize=(6.2,5); change font of both cbar.ax xlabels to fontsize=12; add prefix to file name: font11; and do: matplotlib.rcParams.update({"font.size": 12})')

        ###########################################################
        # TABLES FOR EACWE22
        ###########################################################
    dof_lst = ['x', 'y', 'z', 'rx', 'ry', 'rz']
    my_table2 = pd.DataFrame(columns=['Analysis', 'Type', 'DOF', 'Avg.', 'Min', 'P1', 'P10', 'P50', 'P90', 'P95', 'P99', 'Max'])

    for dof in [1, 2, 3]:
        # Static
        C1_sw_Hw_max_D_loc = np.array([func(np.max(np.abs(C1_Hw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(C1_n_Nw_sw_cases)])
        C2_sw_Hw_max_D_loc = np.array([func(np.max(np.abs(C2_Hw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        C2_sw_Nw_max_D_loc = np.array([func(np.max(np.abs(C2_Nw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        # sw_Nw_Hw_ratio_max_D_loc = sw_Nw_max_D_loc / sw_Hw_max_D_loc
        # Buffeting
        C1_buf_Hw_max_D_loc = np.array([func(np.max(np.abs(C1_std_delta_local['Hw'][case][:n_g_nodes, dof])), dof) for case in range(C1_n_Nw_sw_cases)])
        C2_buf_Hw_max_D_loc = np.array([func(np.max(np.abs(C2_std_delta_local['Hw'][case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        C2_buf_Nw_max_D_loc = np.array([func(np.max(np.abs(C2_std_delta_local['Nw'][case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        # buf_Nw_Hw_ratio_max_D_loc = buf_Nw_max_D_loc / buf_Hw_max_D_loc
        # Static wind
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), [ 'Static',   'C1_Hw', f'{dof_lst[dof]}'] + [np.mean( C1_sw_Hw_max_D_loc)] + np.percentile( C1_sw_Hw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), [ 'Static',   'C2_Hw', f'{dof_lst[dof]}'] + [np.mean( C2_sw_Hw_max_D_loc)] + np.percentile( C2_sw_Hw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), [ 'Static',   'C2_Nw', f'{dof_lst[dof]}'] + [np.mean( C2_sw_Nw_max_D_loc)] + np.percentile( C2_sw_Nw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        # Buffeting
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), ['Buffeting', 'C1_Hw', f'{dof_lst[dof]}'] + [np.mean(C1_buf_Hw_max_D_loc)] + np.percentile(C1_buf_Hw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), ['Buffeting', 'C2_Hw', f'{dof_lst[dof]}'] + [np.mean(C2_buf_Hw_max_D_loc)] + np.percentile(C2_buf_Hw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
        my_table2 = my_table2.append(dict(zip(my_table2.keys(), ['Buffeting', 'C2_Nw', f'{dof_lst[dof]}'] + [np.mean(C2_buf_Nw_max_D_loc)] + np.percentile(C2_buf_Nw_max_D_loc, [0, 1, 10, 50, 90, 95, 99, 100]).tolist())), ignore_index=True)
    my_table2.to_csv(r'results\C1VSC2_Static_and_buffeting_response_stats_Percentiles.csv')

    ########
    ### NEW PLOTS INCLUDING BOX PLOTS ON THE RIGHT SIDE OF THE SCATTER PLOTS W/ RESPECT TO U ####
    ########
    ### STATIC
    str_dof = {'sw': ["$|\Delta_x|_{max}$ $[m]$",
                      "$|\Delta_y|_{max}$ $[m]$",
                      "$|\Delta_z|_{max}$ $[m]$",
                      "$|\Delta_{rx}|_{max}$ $[\degree]$",
                      "$|\Delta_{ry}|_{max}$ $[\degree]$",
                      "$|\Delta_{rz}|_{max}$ $[\degree]$"],
               'buf': ["$\sigma_{x, max}$ $[m]$",
                       "$\sigma_{y, max}$ $[m]$",
                       "$\sigma_{z, max}$ $[m]$",
                       "$\sigma_{rx, max}$ $[\degree]$",
                       "$\sigma_{ry, max}$ $[\degree]$",
                       "$\sigma_{rz, max}$ $[\degree]$"]}
    matplotlib.rcParams.update({'font.size': 14})
    for dof in [1, 2, 3]:
        C1_sw_Hw_max_D_loc = np.array([func(np.max(np.abs(C1_Hw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(C1_n_Nw_sw_cases)])
        C2_sw_Hw_max_D_loc = np.array([func(np.max(np.abs(C2_Hw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        C2_sw_Nw_max_D_loc = np.array([func(np.max(np.abs(C2_Nw_D_loc[case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        fig, (ax1, ax2) = plt.subplots(1, 2, sharex=False, sharey=True, dpi=400, gridspec_kw={'width_ratios': [7, 1]})
        for case in range(C1_n_Nw_sw_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            beta_DB_1_case = beta_DB_func(C1_Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            ax1.scatter(C1_Hw_U_bar[case, 0], func(np.max(np.abs(C1_Hw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow,s=70, alpha=0.5, c='green', edgecolors='none', label=label1)
            ax1.scatter(C2_Hw_U_bar[case, 0], func(np.max(np.abs(C2_Hw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow,s=70, alpha=0.5, c='blue', edgecolors='none', label=label2)
            ax1.scatter(C2_Hw_U_bar[case, 0], func(np.max(np.abs(C2_Nw_D_loc[case][:n_g_nodes, dof])), dof), marker=arrow,s=70, alpha=0.5, c='orange', edgecolors='none', label=label3)
        ax1.set_xlabel(r'$U^H$ [m/s]')
        ax1.set_ylabel(str_dof['sw'][dof])
        ax1.grid()
        # Box plot:
        bplot = ax2.boxplot(x=[C1_sw_Hw_max_D_loc, C2_sw_Hw_max_D_loc, C2_sw_Nw_max_D_loc], notch=True, whis=1E6, patch_artist=True, labels=['CH', 'SH', 'SI'], widths=(0.8,0.8,0.8))
        alpha=0.5
        for patch, color in zip(bplot['boxes'], [matplotlib.colors.to_rgba('green', alpha=alpha), matplotlib.colors.to_rgba('blue', alpha=alpha), matplotlib.colors.to_rgba('orange', alpha=alpha)]):
            patch.set_facecolor(color)
        for median_line_color in bplot['medians']:
            median_line_color.set_color('black')
        for cap in bplot['caps']:
            cap.set(linewidth=1.5, xdata = cap.get_xdata() + (-0.15, +0.15))  # increasing thickness and width of caps
        ax2.yaxis.grid()
        ax2.axis('off')
        plt.ylim(bottom=0)
        fig.tight_layout()
        plt.savefig(rf'results\C1VSC2_sw_scatt_wrtU_Nw_VS_Hw_dof_{dof}_w_box_plots.png')
        plt.show()

    ### BUFFETING
    for dof in [1, 2, 3]:
        C1_buf_Hw_max_D_loc = np.array([func(np.max(np.abs(C1_std_delta_local['Hw'][case][:n_g_nodes, dof])), dof) for case in range(C1_n_Nw_sw_cases)])
        C2_buf_Hw_max_D_loc = np.array([func(np.max(np.abs(C2_std_delta_local['Hw'][case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])
        C2_buf_Nw_max_D_loc = np.array([func(np.max(np.abs(C2_std_delta_local['Nw'][case][:n_g_nodes, dof])), dof) for case in range(C2_n_Nw_sw_cases)])

        fig, (ax1, ax2) = plt.subplots(1, 2, sharex=False, sharey=True, dpi=400, gridspec_kw={'width_ratios': [7, 1]})
        plt.subplots_adjust(wspace=0.05)
        for case in range(C1_n_Nw_sw_cases):
            label1, label2, label3 = ('Cos rule - Homog. (CH)', '3D skew wind - Homog. (SH)', '3D skew wind - Inhomog. (SI)') if case == 0 else (None, None, None)
            beta_DB_1_case = beta_DB_func(C1_Hw_beta_0[case][0])
            arrow = matplotlib.markers.MarkerStyle(marker=my_down_arrow)
            arrow._transform = arrow.get_transform().rotate_deg(deg(-beta_DB_1_case))  # it needs to be a negative rotation because of the convention in rotate_deg() method
            ax1.scatter(C1_Hw_U_bar[case, 0], func(np.max(np.abs(C1_std_delta_local['Hw'][case,:, dof])), dof), marker=arrow,s=70, alpha=0.5, c='green', edgecolors='none', label=label1)
            ax1.scatter(C2_Hw_U_bar[case, 0], func(np.max(np.abs(C2_std_delta_local['Hw'][case,:, dof])), dof), marker=arrow,s=70, alpha=0.5, c='blue', edgecolors='none', label=label2)
            ax1.scatter(C2_Hw_U_bar[case, 0], func(np.max(np.abs(C2_std_delta_local['Nw'][case,:, dof])), dof), marker=arrow,s=70, alpha=0.5, c='orange', edgecolors='none', label=label3)
        ax1.set_xlabel(r'$U^H$ [m/s]')
        ax1.set_ylabel(str_dof['buf'][dof])
        ax1.grid()
        # Box plot:
        bplot = ax2.boxplot(x=[C1_buf_Hw_max_D_loc, C2_buf_Hw_max_D_loc, C2_buf_Nw_max_D_loc], notch=True, whis=1E6, patch_artist=True, labels=['CH', 'SH', 'SI'], widths=(0.8,0.8,0.8))
        alpha=0.5
        for patch, color in zip(bplot['boxes'], [matplotlib.colors.to_rgba('green', alpha=alpha), matplotlib.colors.to_rgba('blue', alpha=alpha), matplotlib.colors.to_rgba('orange', alpha=alpha)]):
            patch.set_facecolor(color)
        for median_line_color in bplot['medians']:
            median_line_color.set_color('black')
        for cap in bplot['caps']:
            cap.set(linewidth=1.5, xdata = cap.get_xdata() + (-0.15, +0.15))  # increasing thickness and width of caps
        ax2.yaxis.grid()
        ax2.axis('off')
        plt.ylim(bottom=0)
        fig.tight_layout()
        plt.savefig(rf'results\C1VSC2_buf_scatt_wrtU_Nw_VS_Hw_dof_{dof}_w_box_plots.png')
        plt.show()


##################################
# SCATTER PLOTS FROM FD_std_delta_max.csv file
##################################
# # Getting the FD results df file
# my_result_path = os.path.join(os.getcwd(), r'results')
# results_paths_FD = []
# for path in os.listdir(my_result_path):
#     if path[:16] == "FD_std_delta_max":
#         results_paths_FD.append(path)
# for obj in list(enumerate(results_paths_FD)): print(obj)  # print list of files for user to choose
# file_idx = input('Select which file to plot:')
# file_to_plot = os.path.join(my_result_path, results_paths_FD[int(file_idx)])
# results_df = pd.read_csv(file_to_plot)
# n_Nw_idxs = results_df['Nw_idx'].max() + 1  # to account for 0 idx
# # Getting the Nw wind properties into the same df
# my_Nw_buf_path = os.path.join(os.getcwd(), r'intermediate_results', 'static_wind')
# Nw_dict_all, Nw_U_bar_RMS, Hw_U_bar_RMS = [], [], []  # RMS = Root Mean Square, such that the U_bar averages along the fjord are energy-equivalent
# for i in range(n_Nw_idxs):
#     Nw_path = os.path.join(my_Nw_buf_path, f'Nw_dict_{i}.json')
#     with open(Nw_path, 'r') as f:
#         Nw_dict_all.append(json.load(f))
#         Nw_U_bar_RMS.append(np.sqrt(np.mean(np.array(Nw_dict_all[i]['Nw_U_bar'])**2)))
#         Hw_U_bar_RMS.append(np.sqrt(np.mean(np.array(Nw_dict_all[i]['Hw_U_bar'])**2)))
# results_df['Nw_U_bar_RMS'] = results_df['Nw_idx'].map(dict((i,j) for i,j in enumerate(Nw_U_bar_RMS)))
# results_df['Hw_U_bar_RMS'] = results_df['Nw_idx'].map(dict((i, j) for i, j in enumerate(Hw_U_bar_RMS)))
# # Plotting
# for dof in [1,2,3]:
#     str_dof = ["$\sigma_{x, max}$ $[m]$",
#                "$\sigma_{y, max}$ $[m]$",
#                "$\sigma_{z, max}$ $[m]$",
#                "$\sigma_{rx, max}$ $[\degree]$",
#                "$\sigma_{ry, max}$ $[\degree]$",
#                "$\sigma_{rz, max}$ $[\degree]$"]
#     Nw_row_bools = results_df['Nw_or_equiv_Hw'] == 'Nw'
#     Hw_row_bools = results_df['Nw_or_equiv_Hw'] == 'Hw'
#     Nw_x, Hw_x = results_df[Nw_row_bools]['Nw_U_bar_RMS'], results_df[Hw_row_bools]['Hw_U_bar_RMS']
#     Nw_y, Hw_y = results_df[Nw_row_bools][f'std_max_dof_{dof}'], results_df[Hw_row_bools][f'std_max_dof_{dof}']
#     if dof >= 3:
#         Nw_y, Hw_y = deg(Nw_y), deg(Hw_y)
#     plt.figure(figsize=(5,5), dpi=300)
#     plt.title(f'Buffeting response ({n_Nw_idxs} worst 1h-events)')
#     plt.scatter(Nw_x, Nw_y, marker='x', s=10, alpha=0.7, c='orange', label='Inhomogeneous')
#     plt.scatter(Hw_x, Hw_y, marker='o', s=10, alpha=0.7, c='blue', label='Homogeneous')
#     plt.ylabel(str_dof[dof])
#     plt.xlabel(r'$\bar{U}_{RMS}$ [m/s]')
#     plt.legend()
#     plt.tight_layout()
#     plt.savefig(rf'results\buf_scatt_Nw_VS_Hw_dof_{dof}.png')
#     plt.show()
