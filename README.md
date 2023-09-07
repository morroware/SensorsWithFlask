# SensorsWithFlask

This repository contains a Raspberry Pi script to read data from a BME280 sensor, log the data to Adafruit IO, and send Slack alerts when necessary.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Hardware Setup](#hardware-setup)
- [Software Setup](#software-setup)
  - [Setting Up Wi-Fi](#setting-up-wi-fi)
  - [Installing Dependencies](#installing-dependencies)
  - [Setting Up the Script](#setting-up-the-script)
  - [Setting Up the Script to Run on Boot](#setting-up-the-script-to-run-on-boot)
- [Usage](#usage)

## Prerequisites

- Raspberry Pi with Raspbian OS installed.
- BME280 sensor.
- Internet connection.
- Slack account (for alerts).
- Adafruit IO account (for logging data).

## Hardware Setup

1. **Connect the BME280 Sensor to the Raspberry Pi:**
   - Connect the \`VCC\` pin of the BME280 to the `3.3V` pin on the Raspberry Pi.
   - Connect the \`GND\` pin of the BME280 to any `GND` pin on the Raspberry Pi.
   - Connect the \`SDA\` pin of the BME280 to the `SDA` pin (GPIO 2) on the Raspberry Pi.
   - Connect the \`SCL\` pin of the BME280 to the `SCL` pin (GPIO 3) on the Raspberry Pi.

2. Power on the Raspberry Pi.

## Software Setup

### Setting Up Wi-Fi

1. Open the terminal on your Raspberry Pi.
2. Navigate to the `wpa_supplicant` configuration file:

   ```bash
   sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
   ```

3. Add the following lines to the end of the file, replacing `YOUR_NETWORK_NAME` and `YOUR_PASSWORD` with your Wi-Fi details:

   ```bash
   network={
       ssid="YOUR_NETWORK_NAME"
       psk="YOUR_PASSWORD"
   }
   ```

4. Save and close the file.
5. Reboot the Raspberry Pi:

   ```bash
   sudo reboot
   ```

### Installing Dependencies

1. Update the package list:

   ```bash
   sudo apt update
   ```

2. Install pip for Python:

   ```bash
   sudo apt install python3-pip
   ```

3. Install the required Python libraries:

   ```bash
   pip3 install flask smbus2 bme280 slack_sdk configparser Adafruit_IO
   ```

### Setting Up the Script

1. Clone the repository:

   ```bash
   git clone https://github.com/morroware/SensorsWithFlask.git
   ```

2. Navigate to the cloned directory:

   ```bash
   cd SensorsWithFlask
   ```

3. Create a `templates` directory:

   ```bash
   mkdir templates
   ```

4. Move the `settings.html` file into the `templates` directory:

   ```bash
   mv settings.html templates
   ```

5. Update the `SingleSensorSettings.conf` file with your specific settings:

   ```bash
   nano SingleSensorSettings.conf
   ```

6. Save and close the file.

### Setting Up the Script to Run on Boot

1. Open the crontab:

   ```bash
   sudo crontab -e
   ```

2. Add the following line to the end of the file to run the script on boot:

   ```bash
   @reboot python3 /path/to/your/SingleSensor.py
   ```

   Replace `/path/to/your/` with the actual path to the `SingleSensor.py` script.

3. Save and close the file.

## Usage

1. Run the `SingleSensor.py` script:

   ```bash
   python3 SingleSensor.py
   ```

2. Access the settings interface via a web browser at `http://<your_pi_ip>:5000/settings`.

**Note:** Make sure to replace `<your_pi_ip>` with the actual IP address of your Raspberry Pi.
