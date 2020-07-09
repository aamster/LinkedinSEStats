import re

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys


class Locator:
    def __init__(self):
        self.driver = webdriver.Chrome()

    def scrape(self, places, place_type=None):
        place_location_map = {}
        for place in places:
            self.driver.get('https://www.google.com/')
            location = self._get_location(place=place, place_type=place_type)
            place_location_map[place] = location

        return place_location_map

    def _get_location(self, place, place_type=None):
        """

        :param place: place to get location for
        :param place_type: should be one of "Address" or "Headquarters"
        :return: address string
        """
        if place_type is not None and place_type not in ['Address', 'Headquarters']:
            raise ValueError('Invalid value for place_type')

        search = self.driver.find_element_by_css_selector('input[title="Search"]')
        search.send_keys(place)
        search.send_keys(Keys.ENTER)
        address = None

        def try_get_address(place_type):
            address = None
            try:
                address_link = self.driver.find_element_by_link_text(place_type)
                parent = address_link.find_element_by_xpath('../..')
                address = parent.find_element_by_css_selector('span:nth-child(2)').text
            except NoSuchElementException:
                pass
            return address

        if place_type is None:
            place_types = ['Address', 'Headquarters']
            for place_type in place_types:
                address = try_get_address(place_type=place_type)
                if address:
                    break
        else:
            address = try_get_address(place_type=place_type)

        return address

    def add_country(self, addresses):
        countries = pd.read_csv('datasets_23752_30346_countries of the world.csv')
        countries['Country'] = countries['Country'].apply(lambda s: s.strip())
        countries = set(countries['Country'])

        def get_country(address, address_country_map):
            address_split = address.split(',')
            # address_split = re.sub(r'[^\w\s]', '', address).split(',')
            address_split = [re.sub(r'\d', '', s) for s in address_split]
            address_split = [s.strip() for s in address_split]
            for s in address_split:
                if s in countries:
                    address_country_map[address] = s
                    return
            address_country_map[address] = 'United States'

        addresses = addresses[addresses.notnull()]

        address_country_map = {}
        addresses.apply(lambda address: get_country(
            address=address, address_country_map=address_country_map))
        return address_country_map


def main():
    school_locator = Locator()
    education = pd.read_csv('education.csv')
    # schools = education['school'].unique()
    # school_location_map = school_locator.scrape(places=schools)
    # education['location'] = education['school'].map(school_location_map)
    # education.to_csv('education.csv', index=False)
    addresses = pd.Series(education['location'].unique())
    address_country_map = school_locator.add_country(addresses=addresses)
    education['Country'] = education['location'].map(address_country_map)
    education.to_csv('education.csv', index=False)


if __name__ == '__main__':
    main()