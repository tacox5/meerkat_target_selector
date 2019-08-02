import sys
import json
import yaml
import time
import threading
import numpy as np
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

        # TODO: handle this in a better way
        self.engine = Triage()

        self.actions = {
            #sensor_alerts actions
            'alerts': self._alerts,
            'sensor_alerts': self._sensor_alerts,

            # alerts actions
            'deconfigure'  : self._deconfigure,

            # sensor actions
            'schedule_block': self._schedule_block,
            'processing': self._processing,
            'observation_status': self._status_update
        }

    def run(self):
        """Runs continuously to listen for messages that come in from specific
           redis channels. Main function that handles the processing of the
           messages that come through redis.
        """
        for item in self.p.listen():
            self._message_to_func(item['channel'])(item['data'])

    def _deconfigure(self, item, sensor_name = 'processing'):
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

            key_glob = '{}:*:{}'.format(self.product_id, sensor)

            for k in self.redis_server.scan_iter(key_glob):
                logger.info('Removing key: {}'.format(k))
                delete_key(self.redis_server, k)


    """

    Interal Methods

    """

    def load_schedule_block(self, message):
        """Reformats schedule block messages and reformats them into dictionary
           format
        """
        message = message.replace('"[', '[')
        message = message.replace(']"', ']')
        return yaml.safe_load(message)


    def _get_sensor_value(product_id, sensor_name):
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
        self.product_id, sensor = self._parse_sensor_name(message)
        self._message_to_func(sensor)(message)

    def _alerts(self, message):
        """Response to alert channel

        # TODO: merge this with sensor_alerts
        """
        # TODO: do something with the product_id
        sensor, product_id = self._parse_sensor_name(message)
        self._message_to_func(sensor)(product_id)

    def _message_to_func(self, channel):
        """Function that selects a function to run based on the channel entered

        Parameters:
            channel: (str)
                channel/sensor name

        Returns:
            Function attached to a particular sensor_name

        """
        return self.actions.get(channel, self._other)

    def _other(self, channel):
        """Function that handles unrecognized requests from redis server

        Parameters:
            item: (dict)
                message passed over redis channel

        Returns:
            None
        """
        logger.warning('Unrecognized channel style: {}'.format(channel))

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

    def _schedule_block(self, key):
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
        target_pointing = schedule_block['targets']
        start_time = schedule_block['actual_start_time']
        start = time.time()

        for i, t in enumerate(target_pointing):
            targs = self.engine.select_targets(*self._parse_pointing(t),
                                                  beam_rad = np.deg2rad(0.5))

            self.engine.add_sources_to_db(targs, t, start_time,
                                          table = 'observation_status')

            self._reformat_df_and_publish(targs.loc[:, ['ra', 'decl', 'priority']],
                                          product_id = product_id, sub_arr_id = i,
                                          sensor_name = 'processing')

        logger.info('{} pointings processed in {} seconds'.format(len(target_pointing),
                                                             time.time() - start))


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
        publish(self.redis_server, 'alerts', key)


    def _parse_pointing(self, t_str):
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
            sensor, value = message.split(':', 1)
            return sensor, value

        except:
            logger.warning('Unrecognized message style: {}')
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
