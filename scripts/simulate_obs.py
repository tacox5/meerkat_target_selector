import numpy as np
import yaml
import matplotlib.pyplot as plt
from mk_target_selector.mk_db import Database_Handler

"""

Things to do:

    1. Incorporate multi-threading into this simulation so that I can run a few
       instances of this program and generate more simulations.
    2.

"""

def manual_search():
    pass

# Parallelize this shtuff

if __name__ == '__main__':

    """

    This section loads the configuration settings from yaml and sets up the
    database connection.

    """
    with open('../config.yaml') as f:
        cfg = yaml.safe_load(f)

    mkdb = Database_Handler(cfg['mysql'])



    """

    This sections loads in all of the pointing information and the approximate
    time spent in each field.

    """

    queue = np.ones(10)



    """

    This section creates a list of targets based on the amount of time on a
    particular project.

    """

    ratio = 0.3 / 0.7
    ra = np.random.uniform(0, 2 * np.pi, size = int(queue.shape[0] * ratio))
    dec = np.random.uniform(0, np.pi, size = int(queue.shape[0] * ratio))


    """
    """

    queue =

    """
    Run the simulation with N random generations of the schedule block
    """

    n_sims = 50

    for _ in np.arange(n_sims):
        # Randomize this somehow
        source_total = 0
        time_total = 0
        n_sources = []
        time = []
        for i in np.arange(queue.shape[0]):
            tb = mkdb.select_targets(queue['ra'][i], queue['dec'][i],
                                beam_rad = 0.5)

            # Test whether or not the source has been observed before
            source_list = mkdb.triage(tb)

            # Add to the database
            mkdb.add_sources_to_db(source_list.loc[:n_beams, :])

            # Store values
            source_total += source_list.shape[0]
            n_sources.append(source_total)
            time_total += queue['time']
            time.append(time_total)

        # Clear the database
        mkdb.conn.execute('DELETE FROM table')
        np.savez(time = np.array(time), n_sources = np.array(n_sources))
