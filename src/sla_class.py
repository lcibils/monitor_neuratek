# -*- coding: utf-8 -*-

import json
from datetime import datetime, timedelta
from icecream import ic

import pandas as pd
from pandas.tseries.offsets import CustomBusinessHour
import holidays

class SLA:
    def __init__(self, sla_file, date_fmt):
        """
        Initialize the SLA class by reading the SLA configuration from a JSON file.
        """
        with open(sla_file, 'r', encoding='utf-8') as file:
            self.config = json.load(file)

        self.categories = [c["name"] for c in self.config["general"]["categories"]]

    def _get_style(self, style, name):
        try: 
            if type(style) is list:
                return [c["style"] for c in style if c['name'] == name][0]
            elif type(style) is dict:
                return style[name]
        except:
            return ''
             
    def style_table(self, name):
        return self._get_style(self.config["general"]['table_style'], name)

    def style_sla(self, name):
        return self._get_style(self.config["general"]['sla_style'], name)

    def style_status(self, name):
        return self._get_style(self.config["general"]['status_style'], name)                  
        
    def style_category(self, name):
        return self._get_style(self.config["general"]['categories'], name) 
    
    def style_customer(self, name):
        return self._get_style(self.config["customers"], name) 

    def _get_customer(self, customer_name):
        customer = next((c for c in self.config["customers"] if c["name"] == customer_name), None)
        if not customer:
            raise ValueError(f"Customer '{customer_name}' not found in SLA configuration.")
        return customer
    
    def _delta(self, customer_name, category, sla_type):
        """
        Get the SLA period as a timedelta for the given customer, incident type, and SLA type.
        """
        customer = self._get_customer(customer_name)
        if customer['service_mode'] != 'None':
            sla_info = customer["sla"]
            if category not in sla_info:
                raise ValueError(f"Incident type '{category}' not found in SLA configuration.")
            if sla_type not in sla_info[category]:
                raise ValueError(f"SLA type '{sla_type}' not found for incident type '{category}'.")

            return int(sla_info[category][sla_type])
        else:
            return 0
    
    def add(self, customer_name, start_time, category, sla_type):
        """
        Add business hours to a given datetime, skipping non-business hours, weekends, and holidays.
        """
        hours_to_add = self._delta(customer_name, category, sla_type)

        if not isinstance(hours_to_add, int) or hours_to_add < 0:
            raise ValueError("hours_to_add must be a non-negative integer.")

        customer = self._get_customer(customer_name)
        if customer['service_mode'] == 'None':
            return pd.NaT

        if customer['service_mode'] == 'partial':
            # Extract parameters from the config
            business_start = customer["business_hours"]["start"]
            business_end = customer["business_hours"]["end"]
            custom_holidays = customer["custom_holidays"]

            # Generate holidays from the `holidays` library
            current_year = datetime.now().year
            holiday_years = [current_year, current_year + 1]
            country_holidays = holidays.Uruguay(years=holiday_years)
            holiday_list = list(country_holidays.keys())

            # Add custom holidays from the config
            holiday_list.extend(pd.Timestamp(date) for date in custom_holidays)

            # Define custom business hours with holidays
            business_hours = CustomBusinessHour(
                start=business_start,
                end=business_end,
                holidays=holiday_list,
                weekmask= customer["business_hours"]["week_mask"]
            )
            result_time = start_time + (hours_to_add * business_hours)
        elif customer['service_mode'] == 'full':
            result_time = start_time + timedelta(hours=hours_to_add)

        return result_time

    def m_c(self, customer_name, f_estimada):
        ''' if customer has SLA use 'Fecha estimada' as SLA TRE'''
        customer = self._get_customer(customer_name)
        if customer['service_mode'] != 'None':
            return f_estimada
    
if __name__ == "__main__":
    sla_file = "sla.json"
    sla = SLA(sla_file)

    # Example query
    customer = "Empresa A"
    incident = "incidente_menor"
    sla_type = "t_resp_est"
    color = "rojo"

    sla_period = sla.delta(customer, incident, sla_type)
    print(f"SLA period for {customer}, {incident}, {sla_type}: {sla_period}")
    print(f"name: incidente_mayor: {sla.name('incidente_mayor')}")
    print(f"color: rojo: {sla.color(color)}")
    
    # Example: Starting on December 10, 2024, at 3 PM
    start_datetime = "2024-12-10 15:00"
    hours_to_add = 10

    resulting_datetime = sla.add(start_datetime, hours_to_add)
    print(f"Resulting datetime: {resulting_datetime}")