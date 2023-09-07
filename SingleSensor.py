# Import necessary libraries and modules
from flask import Flask, request, render_template  # Flask web framework
import time  # For time-related functions
import smbus2  # Interface with I2C devices
import bme280  # Interface with BME280 sensor
from slack_sdk import WebClient  # Communicate with Slack
from slack_sdk.errors import SlackApiError  # Handle Slack errors
import configparser  # Read and write configuration files
from Adafruit_IO import Client  # Interface with Adafruit IO platform
from threading import Thread  # Run tasks in parallel threads
import os  # Interface with the OS, e.g., for rebooting

# Initialize the Flask web application
app = Flask(__name__)

# Define locations for log files
LOG_FILE = "sensor_readings.log"
ERROR_LOG_FILE = "error_log.log"

# Function to read settings from a configuration file
def read_settings_from_conf(conf_file):
    # Initialize a configuration parser
    config = configparser.ConfigParser()
    # Read the configuration file
    config.read(conf_file)
    # Dictionary to store the settings
    settings = {}
    # List of keys we expect in the configuration file
    keys = [
        'SENSOR_LOCATION_NAME', 'MINUTES_BETWEEN_READS', 'SENSOR_THRESHOLD_TEMP',
        'SENSOR_LOWER_THRESHOLD_TEMP', 'THRESHOLD_COUNT', 'SLACK_API_TOKEN',
        'SLACK_CHANNEL', 'ADAFRUIT_IO_USERNAME', 'ADAFRUIT_IO_KEY',
        'ADAFRUIT_IO_GROUP_NAME', 'ADAFRUIT_IO_TEMP_FEED', 'ADAFRUIT_IO_HUMIDITY_FEED'
    ]
    # Extract each key from the configuration file
    for key in keys:
        try:
            # Fetch float values for temperature thresholds
            if key in ['SENSOR_THRESHOLD_TEMP', 'SENSOR_LOWER_THRESHOLD_TEMP']:
                settings[key] = config.getfloat('General', key)
            # Fetch integer values for read intervals and threshold counts
            elif key in ['MINUTES_BETWEEN_READS', 'THRESHOLD_COUNT']:
                settings[key] = config.getint('General', key)
            # Fetch string values for other settings
            else:
                settings[key] = config.get('General', key)
        # Handle missing keys
        except configparser.NoOptionError:
            log_error(f"Missing {key} in configuration file.")
            raise
    # Return the extracted settings
    return settings

# Function to write settings to a configuration file
def write_settings_to_conf(conf_file, settings):
    # Initialize a configuration parser
    config = configparser.ConfigParser()
    # Add the settings to the 'General' section
    config['General'] = settings
    # Write the settings to the configuration file
    with open(conf_file, 'w') as configfile:
        config.write(configfile)

# Function to log errors to an error log file
def log_error(message):
    with open(ERROR_LOG_FILE, 'a') as file:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        file.write(f"{timestamp} - ERROR: {message}\n")

# Function to log sensor readings to a log file
def log_to_file(sensor_name, temperature, humidity):
    with open(LOG_FILE, 'a') as file:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        file.write(f"{timestamp} - {sensor_name} - Temperature: {temperature}°F, Humidity: {humidity}%\n")

# Flask route to handle settings via a web interface
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conf_file = 'SingleSensorSettings.conf'
    if request.method == 'POST':
        # Determine the intended action (save or reboot)
        action = request.form.get('action')
        # Extract the new settings from the form
        new_settings = {key: value for key, value in request.form.items() if key != "action"}
        # Save the new settings to the configuration file
        write_settings_to_conf(conf_file, new_settings)
        # If the action is to reboot, reboot the system
        if action == "reboot":
            os.system('sudo reboot')
        return 'Settings updated!'
    else:
        # Fetch the current settings
        current_settings = read_settings_from_conf(conf_file)
        # Render the settings page with the current settings
        return render_template('settings.html', settings=current_settings)

# Function to continuously monitor sensor readings and send alerts
def run_monitoring():
    # Read initial settings
    settings = read_settings_from_conf('SingleSensorSettings.conf')
    # Store settings in global variables for easy access
    for key, value in settings.items():
        globals()[key] = value

    # Initialize counters and alert flags
    SENSOR_ABOVE_THRESHOLD_COUNT = 0
    SENSOR_ALERT_SENT = False
    SENSOR_BELOW_THRESHOLD_COUNT = 0
    SENSOR_BELOW_ALERT_SENT = False

    # I2C setup for the BME280 sensor
    port = 1
    address_1 = 0x77
    bus_1 = smbus2.SMBus(port)
    calibration_params_1 = bme280.load_calibration_params(bus_1, address_1)

    # Initialize Slack and Adafruit IO clients
    slack_client = WebClient(token=SLACK_API_TOKEN)
    adafruit_io_client = Client(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)

    # Placeholder for alert messages
    sensor_alert_message = ""

    # Continuous monitoring loop
    while True:
        try:
            # Read data from the BME280 sensor
            bme280data_1 = bme280.sample(bus_1, address_1, calibration_params_1)
            # Extract humidity and temperature readings
            humidity_1 = format(bme280data_1.humidity, ".1f")
            temp_c_1 = bme280data_1.temperature
            # Convert temperature to Fahrenheit
            temp_f_1 = (temp_c_1 * 9 / 5) + 32
            # Log the readings to the log file
            log_to_file(SENSOR_LOCATION_NAME, temp_f_1, humidity_1)
            # Send the readings to Adafruit IO
            adafruit_io_client.send(f"{ADAFRUIT_IO_GROUP_NAME}.{ADAFRUIT_IO_TEMP_FEED}", temp_f_1)
            adafruit_io_client.send(f"{ADAFRUIT_IO_GROUP_NAME}.{ADAFRUIT_IO_HUMIDITY_FEED}", humidity_1)
        except Exception as e:
            # Log any errors that occur during data reading or logging
            log_error(f"Error reading or logging data: {e}")

        # Check temperature against thresholds and update alert flags/counters
        if temp_f_1 > SENSOR_THRESHOLD_TEMP:
            SENSOR_ABOVE_THRESHOLD_COUNT += 1
            if SENSOR_ABOVE_THRESHOLD_COUNT >= THRESHOLD_COUNT and not SENSOR_ALERT_SENT:
                # Format the alert message for high temperature
                sensor_alert_message = (
                    f"ALERT: {SENSOR_LOCATION_NAME} Temperature above {SENSOR_THRESHOLD_TEMP}°F\n"
                    f"{SENSOR_LOCATION_NAME} Temperature: {temp_f_1:.1f}°F\n"
                    f"{SENSOR_LOCATION_NAME} Humidity: {humidity_1}%\n"
                )
                SENSOR_ALERT_SENT = True
        elif temp_f_1 < SENSOR_LOWER_THRESHOLD_TEMP:
            SENSOR_BELOW_THRESHOLD_COUNT += 1
            if SENSOR_BELOW_THRESHOLD_COUNT >= THRESHOLD_COUNT and not SENSOR_BELOW_ALERT_SENT:
                # Format the alert message for low temperature
                sensor_alert_message = (
                    f"ALERT: {SENSOR_LOCATION_NAME} Temperature below {SENSOR_LOWER_THRESHOLD_TEMP}°F\n"
                    f"{SENSOR_LOCATION_NAME} Temperature: {temp_f_1:.1f}°F\n"
                    f"{SENSOR_LOCATION_NAME} Humidity: {humidity_1}%\n"
                )
                SENSOR_BELOW_ALERT_SENT = True
        # Reset alert flags and counters when temperature is back in the acceptable range
        elif SENSOR_LOWER_THRESHOLD_TEMP <= temp_f_1 <= SENSOR_THRESHOLD_TEMP and (SENSOR_ALERT_SENT or SENSOR_BELOW_ALERT_SENT):
            sensor_alert_message = (
                f"NOTICE: {SENSOR_LOCATION_NAME} Temperature is now back within range at {temp_f_1:.1f}°F\n"
            )
            SENSOR_ALERT_SENT = False
            SENSOR_BELOW_ALERT_SENT = False
            SENSOR_ABOVE_THRESHOLD_COUNT = 0
            SENSOR_BELOW_THRESHOLD_COUNT = 0

        # Send any alert messages to Slack
        if sensor_alert_message:
            try:
                slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=sensor_alert_message)
            except SlackApiError as e:
                # Log any errors that occur when sending messages to Slack
                log_error(f"Error posting message to Slack: {e}")
            sensor_alert_message = ""

        # Sleep for the specified interval before checking again
        time.sleep(60 * MINUTES_BETWEEN_READS)

# Run the monitoring function in a separate thread so it doesn't block the main Flask app
t = Thread(target=run_monitoring)
t.start()

# Start the Flask app; allows the settings interface to be accessed via a web browser
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
