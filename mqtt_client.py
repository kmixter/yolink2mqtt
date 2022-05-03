import json
import paho.mqtt.client as mqtt
from time import time


class MQTTClient:
    """Creating an MQTT Client to work with the MQTT API

    See https://pypi.org/project/paho-mqtt
    """

    def __init__(self, access_token: str, client_id: str, home_id: str, transport: str = 'tcp'):
        """

        :param access_token:
        :param client_id:
        :param home_id: HomeId retrieved via the HTTP API
        :param transport: 'tcp' or 'websockets'
        """

        # this is required to subscribe to events coming from the devices of the given home
        self.home_id = home_id

        # create an MQTT Client
        self.client = mqtt.Client(client_id=client_id,
                                  clean_session=True,
                                  userdata=None,
                                  protocol=mqtt.MQTTv311,
                                  transport=transport  # websocket or tcp
                                  )
        self.client.username_pw_set(username=access_token)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_log = self.on_log
        self.client.connect(host="api.yosmart.com",
                            port=8003 if transport == 'tcp' else 8004,
                            keepalive=60)

        self.relay = mqtt.Client()
        self.relay.connect('localhost')

        self.relay.on_log = self.on_log

        self.devices = {}
        self.device_configs = {}
        self.device_config_topics = {}

    def on_connect(self, client, userdata, flags, rc):
        """The callback for when the client receives a CONNACK response from the server."""
        print("Connected with result code " + str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(f"yl-home/{self.home_id}/+/report")

    def on_message(self, client, userdata, msg):
        """The callback for when a PUBLISH message is received from the server."""
        print(msg.topic + " " + str(msg.payload))

        # Example door sensor message:
        # {"event":"DoorSensor.Alert","time":1651209111950,"msgid":"1651209111950","data":{"state":"closed","alertType":"normal","battery":4,"version":"041a","loraInfo":{"signal":-34,"gatewayId":"d88b4c1603011a02","gateways":1}},"deviceId":"###"}

        # Example THSensor message:
	#{"event":"THSensor.Report","time":1651210270552,"msgid":"1651210270552","data":{"state":"normal","alarm":{"lowBattery":false,"lowTemp":false,"highTemp":false,"lowHumidity":false,"highHumidity":false,"period":false,"code":0},"battery":3,"mode":"f","interval":0,"temperature":-13.1,"humidity":48.3,"tempLimit":{"max":-3.4,"min":-25.7},"humidityLimit":{"max":100,"min":0},"tempCorrection":0,"humidityCorrection":0,"version":"0392","loraInfo":{"signal":-49,"gatewayId":"d88b4c1603011a02","gateways":1}},"deviceId":"###"}

	# Example MotionSensor messages:
	#{"event":"MotionSensor.Alert","time":1651552712756,"msgid":"1651552712756","data":{"state":"alert","battery":4,"version":"0466","ledAlarm":true,"alertInterval":30,"nomotionDelay":1,"sensitivity":3,"loraInfo":{"signal":-80,"gatewayId":"d88b4c1603011a02","gateways":1}},"deviceId":"###"}
	#{"event":"MotionSensor.StatusChange","time":1651552790870,"msgid":"1651552790869","data":{"state":"normal","battery":4,"version":"0466","ledAlarm":true,"alertInterval":30,"nomotionDelay":1,"sensitivity":3,"loraInfo":{"signal":-78,"gatewayId":"d88b4c1603011a02","gateways":1}},"deviceId":"###"}'

        report = json.loads(msg.payload)
        device_id = report['deviceId']
        if not device_id in self.devices:
            print('Skipping ignored device %s\n' % device_id)
            return

        device = self.devices[device_id]
        topic = self.device_configs[device_id]['state_topic']

        if report['event'] == 'DoorSensor.Alert':
            state = report['data']['state']
            payload = 'ON' if state == 'open' else 'OFF'
        elif report['event'] == 'THSensor.Report':
            payload = report['data']['temperature']
            mode = report['data']['mode'].upper()
            if mode == 'F':
                # Temperature is always reported in C, so convert to F if requested
                payload = round(float(payload) * 1.8 + 32)
            unit_of_measurement = '°' + mode
            config = self.device_configs[device_id]
            config['unit_of_measurement'] = unit_of_measurement
            self.relay.publish(self.device_config_topics[device_id], json.dumps(config, indent=0))
        elif report['event'] == 'MotionSensor.Alert' or report['event'] == 'MotionSensor.StatusChange':
            state = report['data']['state']
            payload = 'ON' if state == 'alert' else 'OFF'
        else:
            print('Unhandled report type: ' + report['event']);
            return

        self.relay.publish(topic, payload)

    def send_discovery(self, device_response):
        print('device response: %s\n' % device_response)
        print('keys %s\n' % device_response.keys())
        for x in device_response['data']['devices']:
            device_id = x['deviceId']
            type = x['type']
            ha_config = {
              'name': x['name'],
              'unique_id': 'yo_' + device_id
            }
            ha_platform = None
            if type == 'DoorSensor':
                ha_platform = 'binary_sensor'
                ha_config['device_class'] = 'door'
            elif type == 'THSensor':
                ha_platform = 'sensor'
                # Default to Fahrenheit, in config, but resend it if the state indicates C.
                ha_config['unit_of_measurement'] = '°F'
            elif type == 'MotionSensor':
                ha_platform = 'binary_sensor'
                ha_config['device_class'] = 'motion'
            else:
                print('Ignoring unhandled device %s' % x['name'])
                next

            topic = f'homeassistant/{ha_platform}/{x["deviceId"]}/config';
            ha_config['state_topic'] = f'homeassistant/{ha_platform}/{x["deviceId"]}/state'
            self.relay.publish(topic, json.dumps(ha_config, indent=0))
            self.devices[device_id] = x
            self.device_configs[device_id] = ha_config
            self.device_config_topics[device_id] = topic

    @classmethod
    def on_log(cls, client, userdata, level, buff):
        print(f"Log from MQTT: {buff}")

    def loop_start(self):
        self.client.loop_start()
        self.relay.loop_start()

    def loop_stop(self):
        self.client.loop_end()
        self.relay.loop_end()
