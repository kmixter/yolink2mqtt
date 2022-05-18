## YoLink2MQTT Integration - Converts YoLink's API to Home Assistant MQTT Discovery

This project is quick modification of github.com/zoltan-fedor/yolink-integration
which enables Home Assistant to access sensors from your YoLink LoRa network.

This is a temporary hack until YoLink has upstream support in Home Assistant.

It uses Python and the YoLink API http://doc.yosmart.com/docs/account/Manage to retrieve
the Access Token and then use the MQTT API of YoLink to subscribe for the sensor's events
and trigger whatever needs to be triggered when a certain event has arrived.

### How to get your YoLink API User Access Credentials?

1. Open the YoLink mobile app (I did it on Android) and open the left sidebar nav.
2. Open Settings > Account > Advanced Settings > User Access Credentials
3. Hit the + sign button in the bottom right and confirm to request access credentials.
4. You should now see a UAID (User Access Id) and Secret Key.
5. You will need to save these into the  `.envs/creds.env` file - see later

### Store your UAID and Secret Key in the `.envs/creds.env` file

Use the `.envs/creds.env.template` file to create a `.envs/creds.env` file and
store your UAID (User Access Id) and Secret Key there. This is from where
Python will be picking up your credentials.

### How to setup the project

Use `pipenv` to setup your Python virtual env within this directory
after cloning it from git:
```
$ pipenv --python 3.10
$ pipenv shell
$ pipenv install
```

### How to set up HomeAssistant

You will need to run the Mosquitto broker on the same device as this script and
Home Assistant.

```
$ sudo apt-get install mosquitto mosquitto-client
$ sudo service mosquitto start
```

Now that it is running, go into Home Assistant and add the "MQTT" integration.
Configure it to use "localhost" and default port 1883.

### To run the integration script

```
# make sure you activate your Python virtual env
$ pipenv shell
(yolink-integration) $ python main.py
```

You will probably want to run this as a service, so it is always running,
which is probably easiest to do with something like `supervisord`.

An example supervisord configuration:
```
[program:yolink2mqtt]
user = pi
environment = SHELL=/bin/bash
directory = /yolink2mqtt
command = pipenv run python main.py
stdout_logfile = /var/log/supervisor/%(program_name)s.log
stderr_logfile = /var/log/supervisor/%(program_name)s.log
autorestart = true
```

As soon as the script starts, the compatible sensors should show up in Home Assistant.
Currently this script supports:
* Door sensor
* Temp/Humidity sensors
* Indoor and outdoor motion sensors
* Vibration sensors (show up as motion sensors)

(Feel free to PR for others, I only have these.)

### Debugging

You can use the following to subscribe to the Mosquitto broker so you can see
the MQTT published topics/messages from this script.
```
$ mosquitto_sub -v -t homeassistant/#
```
