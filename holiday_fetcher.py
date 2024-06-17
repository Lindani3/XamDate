import pandas as pd
from nagerapi import NagerObjectAPI
from enum import Enum
from datetime import datetime, date, timedelta
import calendar
from dateutil.relativedelta import relativedelta
import math
class HolidayFetcher:
    
    retrieval_datetime = None

    def __init__(self, countryCode, startYear, endYear):
        # Check if start year < end year
        if startYear > endYear:
            raise ValueError("start Year must be less than end year")
            
        self.countryCode = countryCode.split("+")
        self.startYear = startYear
        self.endYear = endYear
        self.nager = NagerObjectAPI()
        self.holidays_data = []

    def fetchHolidays(self):
        for country_code in self.countryCode:
            for year in range(self.startYear, self.endYear + 1):
                holidays = self.nager.country(country_code).public_holidays(year)
                for holiday in holidays:
                    self.holidays_data.append({
                        "date": holiday.date.strftime('%Y-%m-%d'),
                        "name": holiday.name,
                        "country_code": country_code,
                        "local_name": holiday.local_name,
                    })
        HolidayFetcher.retrieval_datetime = datetime.now()

    def getHolidaysData(self):
        self.fetchHolidays()
        df = pd.DataFrame(self.holidays_data)
        # = pd.to_datetime()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def getHolidaysBetween(self, country_code, start_date, end_date):
        holidays_df = self.getHolidaysData()
        start_date = start_date
        end_date = end_date
        filtered_holidays = holidays_df[(holidays_df['country_code'] == country_code) &
                                        (holidays_df['date'] >= start_date) &
                                        (holidays_df['date'] <= end_date)]
        return filtered_holidays

class DayCalculations:
    
    def __init__(self, holidays_df, weekend_csv_path):
        self.holidays_df = holidays_df
        self.weekend_csv_path = weekend_csv_path
        self.weekend_data = self.loadWeekendData()
        self.country_weekends = self.mapCountryWeekends()

    def loadWeekendData(self):
        weekend_data = pd.read_csv(self.weekend_csv_path)
        weekend_data['Country Code'] = weekend_data['Country Code'].astype(str).str.lower()
        return weekend_data

    def mapCountryWeekends(self):
        weekend_mapping = {
            "Saturday-Sunday": (5, 6),  # Saturday is 5, Sunday is 6 (in Python's weekday indexing)
            "Friday-Saturday": (4, 5),  # Friday is 4, Saturday is 5
            "Thursday-Friday": (3, 4)   # Weekends falling on Thursday and Friday
        }

        country_weekends = {}
        for _, row in self.weekend_data.iterrows():
            country_code = row["Country Code"].strip().lower()
            weekend_type = row["Weekend Type"]
            if weekend_type in weekend_mapping:
                country_weekends[country_code] = weekend_mapping[weekend_type]
            else:
                raise ValueError(f"Unknown weekend type: {weekend_type}")
        return country_weekends

    def isWeekend(self, country_code, given_date):
        # Normalize country code
        country_code = country_code.strip().lower()
        # Ensure the date is in the correct format
        if isinstance(given_date, datetime):
            given_date = given_date.date()
        elif isinstance(given_date, str):
            given_date = datetime.strptime(given_date, '%Y-%m-%d').date()
        # Check if the given date is a weekend
        if country_code in self.country_weekends:
            return given_date.weekday() in self.country_weekends[country_code]
        else:
            raise ValueError(f"Weekend information not available for country code: {country_code}")
    
    def isBusinessDay(self, country_codes_str, given_date):
        
        country_codes = country_codes_str.split("+")
        for country_code in country_codes:
            if self.isWeekend(country_code, given_date):
                return False
            if given_date in self.holidays_df[self.holidays_df['country_code'] == country_code]['date'].values:
                return False
        return True
    
    def addBusinessDays(self,countryCodesStr, startDate, numBusinessDays):
        
        if numBusinessDays < 0:
            raise ValueError(f"Number of business days must be 0 or more, given: {numBusinessDays}")
            
        # Start with the initial date
        currentDate = startDate
        businessDaysAdded = 0  # Counter for the number of business days added
    
        # If the given date is not a business day and no business days are to be added,
        # find the next business day
        if numBusinessDays == 0 and not self.isBusinessDay(countryCodesStr, currentDate):
            while not self.isBusinessDay(countryCodesStr, currentDate):
                currentDate += timedelta(days=1)  # Move to the next day
            return currentDate  # Return the first business day
    
        # Loop until the required number of business days are added
        while businessDaysAdded < numBusinessDays:
            currentDate += timedelta(days=1)  # Increment by one calendar day
            if self.isBusinessDay(countryCodesStr, currentDate):  # If it's a business day
                businessDaysAdded += 1  # Increment the business days count
    
        return currentDate

    # Define a function to find the last business day in a given month
    def getLastBusinessDateInMonth(self,countryCodesStr, givenDate):
        
        """
        Finds the last business day in a given month for specified countries.
        """
        
        # Determine the last day of the month
        lastDayOfMonth = calendar.monthrange(givenDate.year, givenDate.month)[1]  # Get the last day number
        lastDate = datetime(givenDate.year, givenDate.month, lastDayOfMonth).date()  # Construct the last date
        
        # Backtrack to find the last business day in the month
        while not self.isBusinessDay(countryCodesStr, lastDate):  # If the last day isn't a business day
            lastDate -= timedelta(days=1)  # Move backward by one day
        
        return lastDate  # Return the last business day
    
          
    # Function to determine if a given date is the last business day of its month
    def isLastBusinessDayInMonth(self,countryCodesStr, givenDate):
        date_obj = givenDate
        
        return givenDate == self.getLastBusinessDateInMonth(countryCodesStr,date_obj)
    
    def addTenor(self,countryCodesStr, startDate, tenor, roll, preserveMonthEnd):
       
        tenor = tenor.lower()
       
    
        # Validate the roll parameter
        valid_rolls = {"f", "p", "mf", "mpd"}
        roll = roll.lower()
        if roll not in valid_rolls:
            raise ValueError(f"Invalid roll type: '{roll}'. Expected 'f', 'p', 'mf', or 'mpd'.")
    
        # Validate the preserveMonthEnd parameter
        if isinstance(preserveMonthEnd, str):
            preserveMonthEnd = preserveMonthEnd.strip().lower()
            if preserveMonthEnd == "true":
                preserveMonthEnd = True
            elif preserveMonthEnd == "false":
                preserveMonthEnd = False
            else:
                raise ValueError("The 'preserveMonthEnd' parameter must be 'True' or 'False'.")
        elif not isinstance(preserveMonthEnd, bool):
            raise ValueError("The 'preserveMonthEnd' parameter must be 'True' or 'False'.")
    
        # Determine the raw end date based on the tenor
        unit = tenor[-1]
        amount = int(tenor[:-1])
    
        if unit == "d":
            rawEndDate = startDate + timedelta(days=amount)
        elif unit == "w":
            rawEndDate = startDate + timedelta(weeks=amount)
        elif unit == "m":
            rawEndDate = startDate + relativedelta(months=amount)
        elif unit == "y":
            rawEndDate = startDate + relativedelta(years=amount)
        else:
            raise ValueError(f"Invalid tenor unit: '{unit}'. Expected 'd', 'w', 'm', or 'y'.")
    
        # If preserveMonthEnd is True and the start date is the last business day of its month,
        # adjust the rawEndDate to the last business day of the new month
        if preserveMonthEnd and (unit in ("m", "y")):
            if self.isLastBusinessDayInMonth(countryCodesStr, startDate):
                rawEndDate = self.getLastBusinessDateInMonth(countryCodesStr, rawEndDate)
    
        # Roll adjustment based on the specified roll method
        if self.isBusinessDay(countryCodesStr, rawEndDate):
            finalEndDate = rawEndDate
        else:
            # Handle the different roll behaviors
            if roll == "f":  # Following
                finalEndDate = self.addBusinessDays(countryCodesStr, rawEndDate, 0)  # Move to the next business day
            elif roll == "p":  # Preceding
                while not self.isBusinessDay(countryCodesStr, rawEndDate):
                    rawEndDate -= timedelta(days=1)  # Move backward
                finalEndDate = rawEndDate
            elif roll == "mf":  # Modified Following
                finalEndDate = self.addBusinessDays(countryCodesStr, rawEndDate, 0)  # Move to the following business day
                if finalEndDate.month != rawEndDate.month:  # If in a different month, roll backward
                    finalEndDate = rawEndDate
                    while not self.isBusinessDay(countryCodesStr, finalEndDate):
                        finalEndDate -= timedelta(days=1)
            elif roll == "mpd":  # Modified Preceding
                finalEndDate = rawEndDate
                while not self.isBusinessDay(countryCodesStr, rawEndDate):
                    finalEndDate = rawEndDate
                    rawEndDate -= timedelta(days=1)  # Move backward
    
                if finalEndDate.month != rawEndDate.month:
                    finalEndDate = self.addBusinessDays(countryCodesStr, finalEndDate + timedelta(days=1), 0)  # Move forward
    
        return finalEndDate
            
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from enum import Enum


# Define Enums outside of the class
class DayCountBasis(Enum):
    ACT_360 = 'act/360'
    ACT_365 = 'act/365'
    ACT_ACT = 'act/act'
    THIRTY_360 = '30/360'
    THIRTY_360E = '30E/360'

    @classmethod
    def from_string(cls, basis_str: str):
        normalized_str = basis_str.strip().lower()
        for basis in cls:
            if basis.value == normalized_str:
                return basis
        raise ValueError(f"Invalid basis: {basis_str}")

class DayCountBasis(Enum):
    ANNUALLY = "NACA"
    SEMIANNUALLY = "NACS"
    QUARTERLY = "NACQ"
    MONTHLY = "NACM"
    CONTINUOUSLY = "NACC"
    
    @classmethod
    def frm_string(cls, comp_str: str):
        normalized_str = comp_str.strip().upper()
        for comp in cls:
            if comp.value == normalized_str:
                return comp
        raise ValueError(f"Invalid Compounding: {comp_str}")

    @staticmethod
    def getPeriodsPerYear(comp_enum):
        if comp_enum == "NACA":
            return 1
        elif comp_enum == "NACS":
            return 2
        elif comp_enum == "NACQ":
            return 4
        elif comp_enum == "NACM":
            return 12
        elif comp_enum == "NACW":
            return 52
        elif comp_enum == "NACD":
            return 365

class financialCalculations:
    
    def __init__(self):
        pass

    @staticmethod
    def dayCountFraction(startDate, endDate, basis):
        """
        Calculate day count fractions based on the specified basis.
        """
        if endDate < startDate:
            raise ValueError("endDate cannot be earlier than startDate")
    
        try:
            basis_enum = DayCountBasis.from_string(basis)
        except ValueError as e:
            raise ValueError("Invalid basis provided") from e
            
        days_between = (endDate - startDate).days
        
        if basis_enum == DayCountBasis.ACT_360:
            return days_between / 360.0

        elif basis_enum == DayCountBasis.ACT_365:
            return days_between / 365.0
        
'''
    @staticmethod
    def rateConvert(interestRate, fromCompounding, fromBasis, toCompounding, toBasis):
        from_compounding_enum = Compounding.frm_string(fromCompounding)
        to_compounding_enum = Compounding.frm_string(toCompounding)
    
        x = Compounding.getPeriodsPerYear(fromCompounding)
        y = Compounding.getPeriodsPerYear(toCompounding)
    
        num = fromBasis*x
        dem = toBasis*y
    
        return (((1+interestRate/x)**(num/dem))-1)*y


    @staticmethod
    def discountFactor(startDate, endDate, interestRate, compounding: Compounding, dayCount: Basis):
        """
        Calculate discount factor based on the specified parameters.
        """
        year_fraction = financialCalculations.dayCountFractions(startDate, endDate, dayCount)
        
        if compounding == Compounding.ANNUALLY:
            return 1 / (1 + interestRate * year_fraction)
        elif compounding == Compounding.SEMIANNUALLY:
            return 1 / ((1 + interestRate / 2) ** (2 * year_fraction))
        elif compounding == Compounding.QUARTERLY:
            return 1 / ((1 + interestRate / 4) ** (4 * year_fraction))
        elif compounding == Compounding.MONTHLY:
            return 1 / ((1 + interestRate / 12) ** (12 * year_fraction))
        elif compounding == Compounding.CONTINUOUSLY:
            return 1 / (math.exp(interestRate * year_fraction))
        else:
            raise ValueError(f"Unsupported compounding: {compounding}")

'''
    

          