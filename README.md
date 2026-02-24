# ShellyCloud2CSV
# Shelly 3EM Cloud Data Exporter


A Python command-line tool to fetch and export power consumption data from a **Shelly 3EM** device via the Shelly Cloud API. 

Current state: not working

The script supports fetching both **live status** (instantaneous power, voltage, and total accumulated energy) and **historical consumption data** (hourly Watt-hours) for all three individual phases, exporting the results dynamically to a CSV file.

## Features

* **Live Data:** Retrieves real-time power (W), voltage (V), and total energy (Wh) for each of the 3 phases.
* **Historical Data:** Fetches historical energy consumption (Wh) over a specified date range using the Shelly Cloud V2 API.
* **Auto-Phase Handling:** Automatically queries and aggregates data for all three channels (phases) of the Shelly 3EM.
* **Dynamic CSV Export:** Automatically adjusts CSV columns based on whether you are fetching live data or historical data.
* **Append or Overwrite:** Choose whether to keep building your history in a single file or overwrite it with fresh data.

## Prerequisites

* Python 3.7 or higher
* `requests` library

Install the required dependency using pip:

```bash
pip install requests
