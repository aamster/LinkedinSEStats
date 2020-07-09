import os
import time

import requests
from selenium import webdriver
import pandas as pd
import numpy as np
from selenium.common.exceptions import NoSuchElementException

from selenium.webdriver.chrome.options import Options


class LinkedinScraper:
    """
    Class to parse linkedin profiles.
    """
    def __init__(self):
        self.driver = self._instantiate_driver()
        self.session = self._instantiate_session()
        self.school_hrefs = set()

    def get(self, href):
        """
        Overrides driver.get method. It first checks whether the site is reachable.

        :param href: href to get
        :return: None
        """
        self._wait_until_site_reachable()

        self.driver.get(href)

    def scrape(self, sample_num=500, read_profiles_from_file=True):
        """
        Scrapes Linkedin profiles and save results to csv.

        :param sample_num: sample these many profiles
        :param read_profiles_from_file: If True, will read profiles from a file instead of scraping them
        :return: None
        """
        self.get("https://www.linkedin.com/company/google/people/?facetGeoRegion=us%3A0&keywords=software%20engineer")

        time.sleep(30)

        if read_profiles_from_file and os.path.exists('/tmp/profile_hrefs_full.csv'):
            profile_hrefs = pd.read_csv('/tmp/profile_hrefs_full.csv')["0"].values
        else:
            self._scroll_to_end(scroll_pause_time=2)

            profile_hrefs = self._get_profile_links()
            pd.Series(profile_hrefs).to_csv('/tmp/profile_hrefs_full.csv', index=False)

        experiences = []
        education = []

        if sample_num is not None:
            np.random.seed(1234)
            profile_hrefs = np.random.choice(profile_hrefs, size=sample_num, replace=False)

        for href in profile_hrefs:
            experiences_, education_ = self._parse_profile(href=href)
            experiences.append(experiences_)
            education.append(education_)

        experiences = pd.concat(experiences, ignore_index=True)
        education = pd.concat(education, ignore_index=True)

        # education = self._add_location(school_hrefs=self.school_hrefs, degree_df=education)

        experiences.to_csv('experiences.csv', index=False)
        education.to_csv('education.csv', index=False)

        self.driver.quit()

    def _parse_profile(self, href):
        """
        Parses a single profile for experience and education sections

        :param href: href of profile
        :return: experiences and education dataframes
        """
        self.get(href)
        # name = self.driver.find_element_by_css_selector('ul.pv-top-card--list li:first-child').text
        experience_section = ExperienceSection(driver=self.driver)
        experiences = experience_section.parse()
        experiences['id'] = href

        education_section = EducationSection(driver=self.driver)
        education = education_section.parse(school_hrefs=self.school_hrefs)
        education['id'] = href

        return experiences, education

    @staticmethod
    def _instantiate_driver():
        """
        Instantiates selenium driver

        :return: selenium driver
        """
        # in order to reuse same login session
        options = Options()
        options.add_argument("user-data-dir=/tmp/aamster")
        driver = webdriver.Chrome(options=options)

        return driver

    def _instantiate_session(self):
        """
        Use a requests session to copy selenium cookies to requests session

        :return: requests session
        """
        s = requests.session()
        cookies = self.driver.get_cookies()
        f = requests.cookies.cookiejar_from_dict
        for ck in cookies:
            for k in ck:
                ck[k] = str(ck[k])
            s.cookies.update(f(ck))
        return s

    # from https://stackoverflow.com/questions/20986631/how-can-i-scroll-a-web-page-using-selenium-webdriver-in-python
    def _scroll_to_end(self, scroll_pause_time=0.5):
        """
        Scrolls infinite scroll page to end

        :param scroll_pause_time: time to pause between scrolls
        :return: None
        """
        # Get scroll height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait to load page
            time.sleep(scroll_pause_time)

            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _get_profile_links(self):
        """
        Gets all profile hrefs

        :return: list of profile hrefs
        """
        profile_elements = self.driver.find_elements_by_css_selector(
            'div.org-people-profile-card__profile-info a.ember-view')
        profile_hrefs = set()
        for el in profile_elements:
            profile_hrefs.add(el.get_attribute('href'))

        return list(profile_hrefs)

    def _add_location(self, school_hrefs, degree_df):
        """
        Adds a column for location to degree dataframe

        :param school_hrefs: hrefs of schools
        :param degree_df: dataframe of degree info
        :return: degree dataframe with location added
        """
        school_hrefs_location_map = {}
        # get map of location_href to location
        for school_href in school_hrefs:
            self.get(school_href)
            location = 'UNKOWN'
            try:
                location = self.driver.find_element_by_css_selector('div.org-top-card-summary-info-list__info-item').text
            except NoSuchElementException:
                pass
            school_hrefs_location_map[school_href] = location

        degree_df['location'] = degree_df['school_href'].map(school_hrefs_location_map)
        degree_df = degree_df.drop('school_href', axis=1)

        return degree_df

    def _wait_until_site_reachable(self):
        """
        Linkedin prevents too many requests in a short amount of time.
        Check whether site is reachable.
        :return: None
        """
        while True:
            r = self.session.get('https://www.linkedin.com/')
            if r.status_code == 200:
                break
            else:
                time.sleep(60)


class Experience:
    def __init__(self, title, company, date_range, location, description):
        self.title = title
        self.company = company
        self.date_range = date_range
        self.location = location
        self.description = description

    def to_dict(self):
        """
        Converts object to dict

        :return: dict
        """
        return {
            'title': self.title,
            'company': self.company,
            'date_range': self.date_range,
            'location': self.location,
            'description': self.description
        }


class ExperienceSection:
    def __init__(self, driver):
        self.driver = driver

    @staticmethod
    def parse_single(experience, company=None, is_multi_role=False):
        """
        Parses single experience section

        :param experience: experience selenium tag
        :param company: can give a company (useful for multiple roles)
        :param is_multi_role: Whether multiple roles, same company
        :return: Experience
        """
        title = ''
        date_range = ''
        location = ''
        description = ''

        try:
            if is_multi_role:
                title = experience.find_element_by_css_selector('span:nth-child(2)').text
            else:
                title = experience.find_element_by_css_selector('h3:first-child').text
        except NoSuchElementException:
            pass

        try:
            if company is None:
                company = experience.find_element_by_css_selector('p.pv-entity__secondary-title').text
        except NoSuchElementException:
            pass

        try:
            date_range = experience.find_element_by_css_selector('h4.pv-entity__date-range span:nth-child(2)').text
        except NoSuchElementException:
            pass

        try:
            location = experience.find_element_by_css_selector('h4.pv-entity__location span:nth-child(2)').text
        except NoSuchElementException:
            pass

        # parent = experience.find_element_by_xpath('../..')
        # try:
        #     description = parent.find_element_by_css_selector(
        #         'div.pv-entity__extra-details p.pv-entity__description').text
        # except NoSuchElementException:
        #     pass

        experience = Experience(title=title, company=company, date_range=date_range, location=location,
                                description=description)

        return experience

    def parse(self):
        """
        Parses all experience sections in profile

        :return: Dataframe of experiences
        """
        try:
            see_more_btn = self.driver.find_element_by_css_selector('button.pv-profile-section__see-more-inline')
            see_more_btn.click()
        except:
            pass

        res = []

        experiences = self.driver.find_elements_by_css_selector(
            'section#experience-section section.pv-profile-section__card-item-v2')

        for experience in experiences:
            roles = experience.find_elements_by_css_selector('div.pv-entity__summary-info-v2')
            if len(roles) > 0:
                company = experience.find_element_by_css_selector(
                    'div.pv-entity__company-summary-info h3 span:nth-child(2)').text
                for role in roles:
                    experience = self.parse_single(experience=role, company=company, is_multi_role=True)
                    res.append(experience.to_dict())
            else:
                role = experience.find_element_by_css_selector('div.pv-entity__summary-info')
                experience = self.parse_single(experience=role)
                res.append(experience.to_dict())

        return pd.DataFrame(res)


class Education:
    def __init__(self, school, degree, field_of_study, start, end, school_href):
        self.school = school
        self.degree = degree
        self.field_of_study = field_of_study
        self.start = start
        self.end = end
        self.school_href = school_href

    def to_dict(self):
        """
        Converts object to dict

        :return: dict
        """
        return {
            'school': self.school,
            'degree': self.degree,
            'field_of_study': self.field_of_study,
            'start': self.start,
            'end': self.end,
            'school_href': self.school_href
        }


class EducationSection:
    def __init__(self, driver):
        self.driver = driver

    def parse(self, school_hrefs):
        """
        Parses education sections

        :param school_hrefs: used to collect school hrefs for all schools
        :return: Dataframe of education
        """
        res = []

        degrees = self.driver.find_elements_by_css_selector(
            'section#education-section div.pv-entity__summary-info')

        for degree_section in degrees:
            degree = self._parse_single(degree=degree_section)
            res.append(degree.to_dict())
            school_hrefs.add(degree.school_href)

        df = pd.DataFrame(res)

        return df

    def _parse_single(self, degree):
        """
        Parse a single education section

        :param degree: selenium degree tag
        :return: Education
        """
        school_name = ''
        degree_type = ''
        field_of_study = ''
        date_range_start = None
        date_range_end = None
        location_href = ''

        try:
            school_name = degree.find_element_by_css_selector('h3.pv-entity__school-name').text
        except NoSuchElementException:
            pass

        try:
            degree_type = degree.find_element_by_css_selector('p.pv-entity__degree-name span:nth-child(2)').text
        except NoSuchElementException:
            pass

        try:
            field_of_study = degree.find_element_by_css_selector('p.pv-entity__fos span:nth-child(2)').text
        except NoSuchElementException:
            pass

        try:
            date_range_start = degree.find_element_by_css_selector(
                'p.pv-entity__dates span:nth-child(2) time:nth-child(1)').text
            date_range_end = degree.find_element_by_css_selector(
                'p.pv-entity__dates span:nth-child(2) time:nth-child(2)').text
        except NoSuchElementException:
            pass

        parent = degree.find_element_by_xpath('../..')
        try:
            location_href = parent.find_element_by_css_selector('a.ember-view').get_attribute('href')
        except NoSuchElementException:
            pass

        education = Education(school=school_name, degree=degree_type, field_of_study=field_of_study,
                              start=date_range_start, end=date_range_end, school_href=location_href)
        return education


def main():
    linkedin_scraper = LinkedinScraper()
    linkedin_scraper.scrape(sample_num=5)


if __name__ == '__main__':
    main()
