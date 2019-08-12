import matplotlib.pyplot as plt
import pickle
import numpy as np
import pandas as pd
import glob
import os
import time

targets = pd.read_csv('../../../reduced_target_list.csv')
targets = targets.rename(columns={'Unnamed: 0':'id'})
labels = ['Mhongoose', 'LADUMA', 'Fornax', 'MeerTime MSP',
          'MeerTime Binary', 'MeerTime 1000 PTA', 'MeerTime Globular Clusters',
          'TRAPUM Globular Clusters', 'TRAPUM Fermi','TRAPUM Nearby Galaxies',
          'Mightee L-band', 'Mightee S-band', 'MALS']
idx = np.argsort(labels)
labels = np.array(labels)[idx]

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 2 * np.rad2deg(np.arcsin(np.sqrt(a)))

def random_pointing(ra1 = 0.0, dec1 = -np.pi / 2.0, ra2 = 2 * np.pi, dec2 = np.pi / 4.0):
    """Random pointing in the MeerKAT field of view
    """
    return np.random.uniform(low = ra1, high = ra2), np.random.uniform(low = dec1, high = dec2)

def load_source_dict(save_dict = 'True'):
    """Loads sources within each field
    """
    if os.path.exists('../sim_data/coordinate_dict_id.pkl'):
        with open('../sim_data/coordinate_dict_id.pkl', 'rb') as f:
            project_sources = pickle.load(f)
    else:
        files = np.sort(glob.glob('../sim_data/*csv'))

        project_coords = {}

        for i, f in enumerate(files):
            tb = pd.read_csv(f)
            project_coords[labels[i]] = tb.loc[:, ['ra_deg', 'dec_deg']]

        project_sources = {}

        for key, value in project_coords.items():
            project_sources[key] = []
            print (key)
            for row in value.iterrows():
                in_view = haversine(row[1]['ra_deg'], row[1]['dec_deg'], targets.loc[:, 'ra'], targets.loc[:, 'decl']) < 0.5
                project_sources[key].append(targets.loc[in_view, ['source_id']])

        if save_dict:
            with open('../sim_data/coordinate_dict_id.pkl', 'wb') as f:
                pickle.dump(project_sources, f)

    return project_sources

def set_schedule(obs_time_blocks, idx):
    """Returns schedule based on total amount of observing time for each lsp

    Parameters:
        obs_time_blocks: (float)
            time resolution of observing blocks
    """
    lsp_time = np.array([1650, 3424, 900, 2160, 1440, 720, 1080, 320,
                         338, 226, 979, 948, 1650]) * 3600. # Time in seconds
    lsp_time = lsp_time[idx]
    disc_time = 0.3 / 0.7 * lsp_time.sum()
    alloted_time = np.append(lsp_time, disc_time)
    total_time = lsp_time.sum() + disc_time
    prob = np.append(lsp_time, disc_time) / total_time

    schedule = []

    for i in range(int(total_time / obs_time_blocks)):
        idx = np.random.choice(np.arange(prob.shape[0]), p = prob)
        schedule.append(idx)
        alloted_time[idx] -= obs_time_blocks
        total_time -= obs_time_blocks
        prob = alloted_time / total_time
        if np.any(prob[prob < 0]):
            prob[prob < 0] = 0

    return np.array(schedule)

def run_sim(project_sources, schedule, n_beams = 64, obs_time = 30. * 60., save_sim = True,
            file_name = 'obs_sim.npy'):
    observed_sources = np.array([])
    tot_sources = int(n_beams * obs_time / (5. * 60.))
    tot_sources_observed = 0
    source_list = []

    start = time.time()

    for i, p_idx in enumerate(schedule):
        if i % 1000 == 0 and not i == 0:
            end = time.time()
            print (i, end-start)
            start = end
            plt.plot(np.array(source_list))
            plt.savefig('progress_{}.png'.format(n_beams), dpi = 100)

        source_list.append(tot_sources_observed)

        if p_idx == 13:
            ra, dec = random_pointing()
            in_view = haversine(ra, dec, targets.loc[:, 'ra'], targets.loc[:, 'decl']) < 0.5
            pointing = targets.loc[in_view, ['id']]

        else:
            fields = project_sources[labels[p_idx]]
            pointing = fields[np.random.randint(len(fields))]

        unobserved_sources = pointing.loc[~pointing.isin(observed_sources).id, :]
        srcs = np.array(unobserved_sources.iloc[:tot_sources, :]).ravel()
        tot_sources_observed += srcs.shape[0]
        observed_sources = np.append(observed_sources,srcs)


    if save_sim:
        np.save('obs_sim_{}_beams'.format(n_beams), source_list)


if __name__ == '__main__':
    project_sources = load_source_dict()
    schedule = set_schedule(30. * 60., idx)
    run_sim(project_sources, schedule, n_beams = 128)
