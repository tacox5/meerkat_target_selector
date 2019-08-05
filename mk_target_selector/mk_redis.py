import sys
import json
import yaml
import time
import threading
import numpy as np
from datetime import datetime
from astropy import units as u
from astropy.coordinates import Angle

try:
    from .helper import add_time
    from .logger import log as logger
    from .mk_db import Triage
    from .redis_tools import (publish,
                              get_redis_key,
                              write_pair_redis,
                              connect_to_redis,
                              delete_key)

except ImportError:
    from helper import add_time
    from logger import log as logger
    from mk_db import Triage
    from redis_tools import (publish,
                             get_redis_key,
                             write_pair_redis,
                             connect_to_redis,
                             delete_key)

class Listen(threading.Thread):
    """

    Class for handling redis subscriptions. Takes advantage of the
    threading.Thread subclass to listen for messages in a separate process.

    Examples:
        >>> r = Listen(['alerts', 'sensor_alerts'])
        >>> r.start()

    """
    def __init__(self, chan = ['sensor_alerts', 'alerts']):
        threading.Thread.__init__(self)
        self.redis_server = connect_to_redis()
        self.p = self.redis_server.pubsub(ignore_subscribe_messages = True)
        self.p.psubscribe(chan)

        # Triaging Sources
        self.engine = Triage()

        # TODO: replace this once a more permanent fix is found. Meant to handle
        # the "deconfigure before configuration message" error
        self.product_ids = []

        self.channel_actions = {
            #sensor_alerts actions
            'alerts': self._alerts,
            'sensor_alerts': self._sensor_alerts,
        }

        self.alert_actions = {
            'deconfigure'  : self._deconfigure,
            'configure': self._pass,
            'conf_complete': self._pass,
            'capture-init': self._pass,
            'capture-start': self._pass,
            'capture-stop': self._pass,
            'capture-done': self._pass
        }

        self.sensor_actions = {
            'data_suspect': self._data_suspect,
            'schedule_blocks': self._schedule_blocks,
            'processing': self._processing,
            'observation_status': self._status_update
        }

    def run(self):
        """Runs continuously to listen for messages that come in from specific
           redis channels. Main function that handles the processing of the
           messages that come through redis.
        """
        for item in self.p.listen():
            self._message_to_func(item['channel'], self.channel_actions)(item['data'])



    """

    Alert Functions

    """

    def _alerts(self, message):
        """Response to alert channel
        """
        # TODO: do something with the product_id
        sensor, product_id = self._parse_sensor_name(message)
        self._message_to_func(sensor, self.alert_actions)(product_id)

    def _pass(self, item):
        # Temporary function to handle alert messages
        return 0

    def _deconfigure(self, item):
        """Response to deconfigure message from the redis alerts channel

        Parameters:
            item: (str)
                place holder argument

        Returns:
            None
        """
        # TODO: think of a way to handle multiple sub-array (product_ids) at one time
        sensor_list = ['processing', 'targets']

        for sensor in sensor_list:
            # TODO: Fix this so that if a deconfigure message comes through before
            # a configure message, the target selector won't shutdown
            key_glob = '{}:*:{}'.format(item, sensor)

            for k in self.redis_server.scan_iter(key_glob):
                logger.info('Deconfigure message. Removing key: {}'.format(k))
                delete_key(self.redis_server, k)


    """

    Sensor Alerts Functions

    """

    def _sensor_alerts(self, message):
        """Response to sensor_alerts channel. Runs a function based on the input
        message

        Parameters:
            message: (str)
                Message received from listening to the sensor_alerts channel

        Returns:
            None
        """
        # TODO: do something with the product_id
        product_id, sensor = self._parse_sensor_name(message)

        # TODO: SUPER HACKY CHANGE THIS AS SOON AS POSSIBLE
        if product_id.endswith('_data_suspect'):
            return

        if product_id not in self.product_ids:
            self.product_ids.append(product_id)

        self._message_to_func(sensor, self.sensor_actions)(message)

    def _schedule_blocks(self, key):
        """Block that responds to schedule block updates. Searches for targets
           and publishes the information to the processing channel

           Parameters:
                msg: (dict)
                    Redis channel message received from listening to a channel

            Returns:
                None
        """
        message = get_redis_key(self.redis_server, key)
        product_id = key.split(':')[0]
        schedule_block = self.load_schedule_block(message)

        if isinstance(schedule_block, list):
            if isinstance(schedule_block[0], list):
                target_pointing = schedule_block[0]
            elif isinstance(schedule_block[0], dict):
                target_pointing = schedule_block

        if isinstance(schedule_block, dict):
            target_pointing = schedule_block['targets']

        start = time.time()
        # TODO: Fix this as soon as possible!!!
        start_time = datetime.now()
        for i, t in enumerate(target_pointing):
            targets = self.engine.select_targets(*self.pointing_coords(t),
                                                  beam_rad = np.deg2rad(0.5))

            # TODO: replace with data_suspect, more accurate
            self.engine.add_sources_to_db(targets, t, start_time,
                                          table = 'observation_status')

            self._reformat_df_and_publish(targets.loc[:, ['ra', 'decl']],
                                          product_id = product_id, sub_arr_id = i)

        logger.info('{} pointings processed in {} seconds'.format(len(target_pointing),
                                                             time.time() - start))

    def _data_suspect(self, msg):
        # TODO: use this function to time observations
        return time.time()



    """

    Internal Methods

    """

    def load_schedule_block(self, message):
        """Reformats schedule block messages and reformats them into dictionary
           format
        """
        message = message.replace('"[', '[')
        message = message.replace(']"', ']')
        return yaml.safe_load(message)


    def _get_sensor_value(self, product_id, sensor_name):
        """Returns the value for a given sensor and product id number

        Parameters:
            product_id: (str)
                ID received from redis message
            sensor_name: (str)
                Name of the sensor to be queried

        Returns:
            value: (str, int)
                Value attached to the key in the redis database
        """
        key = '{}:{}'.format(product_id, sensor_name)
        value = get_redis_key(self.redis_server, key)
        return value

    def _message_to_func(self, channel, action):
        """Function that selects a function to run based on the channel entered

        Parameters:
            channel: (str)
                channel/sensor name

        Returns:
            Function attached to a particular sensor_name

        """
        return action.get(channel, self._other)

    def _other(self, channel):
        """Function that handles unrecognized requests from redis server

        Parameters:
            item: (dict)
                message passed over redis channel

        Returns:
            None
        """
        logger.info('Unrecognized channel style: {}'.format(channel))

    def _status_update(self, msg):
        """Function to test the status_update from the processing nodes.

        Parameters:
            msg: (str)
                string formatted like a
        """
        status_msg = self.load_schedule_block(msg)
        if status_msg['success']:
            self.engine.update_obs_status(**status_msg)

    def _processing(self, msg):
        """
        Function to test the processing message. Publishes a success/failure
        message to observation_status channel.
        """
        sources = self.load_schedule_block(msg)
        for id in sources['source_id']:
            success = np.random.choice([1, 0], p = [.4,.6])
            message = {
                'source_id': id, 'success': success,
                'obs_start_time': sources['obs_start_time']
            }
            publish(self.redis_server, 'observation_status', json.dumps(message))
        logger.info('Sources in the current block published to processing')

    def _unsubscribe(self, channels = None):
        """Unsubscribe from the redis server

        Parameters:
            channels: (str, list)
                List of channels you wish to unsubscribe to
        """
        if channels is None:
            self.p.unsubscribe()
        else:
            self.p.unsubscribe(channels)

        logger.info('Unsubscribed from channel(s)')

    def _beam_radius(self, product_id, dish_size = 13.5):
        """Returns the beam radius based on the frequency band used in the
           observation

           Parameters:
                product_id: (str)
                    product ID for the given sub-array

            Returns:
                beam_rad: (float)
                    Radius of the beam in radians
        """
        # TODO: change this to the real name
        sensor_name = 'max_freq'
        key = '{}:{}'.format(product_id, sensor_name)
        max_freq = get_redis_key(self.redis_server, key)
        return (2.998e8 / max_freq) / dish_size

    def _reformat_df_and_publish(self, tb, product_id, sub_arr_id = 1,
                                 sensor_name = 'targets'):
        """Reformat the table returned from target searching

        Parameters:
            tb: (pandas.DataFrame)
                Target information
            t: (dict)
                Information about the telescope pointing
            start_time: (str)
                Beginning of the observation

        Returns:
            None
        """
        targ_dict = tb.to_dict('list')
        key = '{}:block_{}:{}'.format(product_id, sub_arr_id, sensor_name)
        write_pair_redis(self.redis_server, key, json.dumps(targ_dict))

        publish(self.redis_server, 'bluse:///set', key)


    def pointing_coords(self, t_str):
        """Function used to clean up run loop and parse pointing information

        Parameters:
            t_str: (dict)
                schedule block telescope pointing information

        Returns:
            c_ra, c_dec: (float)
                pointing coordinates of the telescope
        """
        pointing = t_str['target'].split(', ')
        c_ra = Angle(pointing[-2], unit=u.hourangle).rad
        c_dec = Angle(pointing[-1], unit=u.deg).rad
        return c_ra, c_dec

    def _parse_sensor_name(self, message):
        """Parse channel name sent over redis channel

        Parameters:
            channel: (str)
                Name of the channel coming over the

        Returns:
            sensor: (str)
                Name of the sensor attached to the message
            value: (str)
                Value of the particular sensor
        """
        try:
            if len(message.split(':')) == 3:
                # TODO: do something with this value
                product_id, sensor, value = message.split(':')
            if len(message.split(':')) == 2:
                product_id, sensor = message.split(':')

            return product_id, sensor

        except:
            logger.warning('Parsing sensor name failed. Unrecognized message \
                            style: {}'.format(message))
            # TODO: Add something that makes more sense
            return False

    def _found_aliens():
        """You found aliens! Alerting slack

        Parameters:
            None

        Returns:
            None
        """
        try:
            from .slack_tools import notify_slack
        except ImportError:
            from slack_tools import notify_slack

        notify_slack()
