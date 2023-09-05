from flask import Flask, request, render_template
import time
import smbus2
import bme280
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import configparser
from Adafruit_IO import Client
from threading import Thread

# Initialize the Flask application
app = Flask(__name__)

# Define log file locations
LOG_FILE = "sensor_readings.log"
ERROR_LOG_FILE = "error_log.log"

# Function to read settings from the configuration file
def read_settings_from_conf(conf_file):
    config = configparser.ConfigParser()
    config.read(conf_file)
    settings = {}
    keys = [
        'SENSOR_LOCATION_NAME', 'MINUTES_BETWEEN_READS', 'SLACK_API_TOKEN',
        'SLACK_CHANNEL', 'SLACK_USERS_TO_TAG', 'SENSOR_THRESHOLD_TEMP',
        'SENSOR_LOWER_THRESHOLD_TEMP', 'THRESHOLD_COUNT',
        'ADAFRUIT_IO_USERNAME', 'ADAFRUIT_IO_KEY',
        'ADAFRUIT_IO_GROUP_NAME', 'ADAFRUIT_IO_TEMP_FEED', 'ADAFRUIT_IO_HUMIDITY_FEED'
    ]
    for key in keys:
        try:
            if key in ['SENSOR_THRESHOLD_TEMP', 'SENSOR_LOWER_THRESHOLD_TEMP']:
                settings[key] = config.getfloat('General', key)
            elif key in ['MINUTES_BETWEEN_READS', 'THRESHOLD_COUNT']:
                settings[key] = config.getint('General', key)
            elif key == 'SLACK_USERS_TO_TAG':
                settings[key] = config.get('General', key).split()
            else:
                settings[key] = config.get('General', key)
        except configparser.NoOptionError:
            log_error(f"Missing {key} in configuration file.")
            raise
    return settings

# Function to write settings to configuration file
def write_settings_to_conf(conf_file, settings):
    config = configparser.ConfigParser()
    config['General'] = settings
    with open(conf_file, 'w') as configfile:
        config.write(configfile)

# Function to log errors
def log_error(message):
    with open(ERROR_LOG_FILE, 'a') as file:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        file.write(f"{timestamp} - ERROR: {message}\n")

# Function to log sensor readings
def log_to_file(sensor_name, temperature, humidity):
    with open(LOG_FILE, 'a') as file:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        file.write(f"{timestamp} - {sensor_name} - Temperature: {temperature}°F, Humidity: {humidity}%\n")

# Flask route for the settings form
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conf_file = 'SingleSensorSettings.conf'
    if request.method == 'POST':
        new_settings = request.form.to_dict()
        write_settings_to_conf(conf_file, new_settings)
        return 'Settings updated!'
    else:
        current_settings = read_settings_from_conf(conf_file)
        return render_template('settings.html', settings=current_settings)

# Function to run the main monitoring loop
def run_monitoring():
    settings = read_settings_from_conf('SingleSensorSettings.conf')
    for key, value in settings.items():
        globals()[key] = value

    # Initialization
    SENSOR_ABOVE_THRESHOLD_COUNT = 0
    SENSOR_ALERT_SENT = False
    SENSOR_BELOW_THRESHOLD_COUNT = 0
    SENSOR_BELOW_ALERT_SENT = False

    port = 1
    address_1 = 0x77
    bus_1 = smbus2.SMBus(port)
    calibration_params_1 = bme280.load_calibration_params(bus_1, address_1)
    slack_client = WebClient(token=SLACK_API_TOKEN)
    adafruit_io_client = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
    sensor_alert_message = ""

    # Main loop
    while True:
        try:
            bme280data_1 = bme280.sample(bus_1, address_1, calibration_params_1)
            humidity_1 = format(bme280data_1.humidity, ".1f")
            temp_c_1 = bme280data_1.temperature
            temp_f_1 = (temp_c_1 * 9 / 5) + 32
            log_to_file(SENSOR_LOCATION_NAME, temp_f_1, humidity_1)
            adafruit_io_client.send(f"{ADAFRUIT_IO_GROUP_NAME}.{ADAFRUIT_IO_TEMP_FEED}", temp_f_1)
            adafruit_io_client.send(f"{ADAFRUIT_IO_GROUP_NAME}.{ADAFRUIT_IO_HUMIDITY_FEED}", humidity_1)

        except Exception as e:
            log_error(f"Error reading or logging data: {e}")

        # Check if temperature exceeds upper threshold
        if temp_f_1 > SENSOR_THRESHOLD_TEMP:
            SENSOR_ABOVE_THRESHOLD_COUNT += 1
            if SENSOR_ABOVE_THRESHOLD_COUNT >= THRESHOLD_COUNT and not SENSOR_ALERT_SENT:
                sensor_alert_message = (
                    f"ALERT: {SENSOR_LOCATION_NAME} Temperature above {SENSOR_THRESHOLD_TEMP}°F\n"
                    f"{SENSOR_LOCATION_NAME} Temperature: {temp_f_1:.1f}°F\n"
                    f"{SENSOR_LOCATION_NAME} Humidity: {humidity_1}%\n"
                )
                SENSOR_ALERT_SENT = True

        # Check if temperature is below the lower threshold
        elif temp_f_1 < SENSOR_LOWER_THRESHOLD_TEMP:
            SENSOR_BELOW_THRESHOLD_COUNT += 1
            if SENSOR_BELOW_THRESHOLD_COUNT >= THRESHOLD_COUNT and not SENSOR_BELOW_ALERT_SENT:
                sensor_alert_message = (
                    f"ALERT: {SENSOR_LOCATION_NAME} Temperature below {SENSOR_LOWER_THRESHOLD_TEMP}°F\n"
                    f"{SENSOR_LOCATION_NAME} Temperature: {temp_f_1:.1f}°F\n"
                    f"{SENSOR_LOCATION_NAME} Humidity: {humidity_1}%\n"
                )
                SENSOR_BELOW_ALERT_SENT = True

        # Reset alert and counters if temperature is back to normal
        elif SENSOR_LOWER_THRESHOLD_TEMP <= temp_f_1 <= SENSOR_THRESHOLD_TEMP and (SENSOR_ALERT_SENT or SENSOR_BELOW_ALERT_SENT):
            sensor_alert_message = (
                f"NOTICE: {SENSOR_LOCATION_NAME} Temperature is now back within range at {temp_f_1:.1f}°F\n"
            )
            SENSOR_ALERT_SENT = False
            SENSOR_BELOW_ALERT_SENT = False
            SENSOR_ABOVE_THRESHOLD_COUNT = 0
            SENSOR_BELOW_THRESHOLD_COUNT = 0

        if sensor_alert_message:
            try:
                tagged_users = " ".join(SLACK_USERS_TO_TAG)
                combined_message_with_tags = f"{tagged_users} {sensor_alert_message}"
                slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=combined_message_with_tags)
            except SlackApiError as e:
                log_error(f"Error posting message to Slack: {e}")

            sensor_alert_message = ""

        time.sleep(60 * MINUTES_BETWEEN_READS)

# Run the monitoring function in a separate thread
t = Thread(target=run_monitoring)
t.start()

# Start the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
