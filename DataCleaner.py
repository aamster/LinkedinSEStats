import pandas as pd

from Locator import Locator


class DataCleaner:
    def __init__(self, education, experiences):
        self.education = education
        self.experiences = experiences

    def clean(self):
        company_most_freq_loc = \
        self.experiences.groupby(['company', 'location']).size().reset_index().sort_values(0, ascending=False).groupby(
            'company')['location'].apply(lambda loc: loc.iloc[0])

        self.experiences.loc[self.experiences['location'].isnull(), 'location'] = (
            self.experiences.loc[self.experiences['location'].isnull()]['company'].map(company_most_freq_loc)
        )

        id_most_freq_loc = \
        self.experiences.groupby(['id', 'location']).size().reset_index().sort_values(0, ascending=False).groupby(
            'id')['location'].apply(lambda loc: loc.iloc[0])

        self.experiences.loc[self.experiences['location'].isnull(), 'location'] = (
            self.experiences.loc[self.experiences['location'].isnull()]['id'].map(id_most_freq_loc)
        )

        # from_, to_ = self.clean_dates(dates=self.experiences['date_range'])
        # self.experiences['from'] = from_
        # self.experiences['to'] = to_
        # del self.experiences['date_range']

        locator = Locator()
        addresses = pd.Series(self.experiences['location'].unique())
        address_country_map = locator.add_country(addresses=addresses)
        self.experiences['Country'] = self.experiences['location'].map(address_country_map)

        addresses = pd.Series(self.education['location'].unique())
        address_country_map = locator.add_country(addresses=addresses)
        self.education['Country'] = self.education['location'].map(address_country_map)

        self.experiences.to_csv('experiences.csv', index=False)
        self.education.to_csv('education.csv', index=False)

    def clean_dates(self, dates):
        date_range_split = dates.str.split('–')
        date_range_split[date_range_split.notnull()] = \
            date_range_split[date_range_split.notnull()].apply(lambda x: [s.strip() for s in x])
        from_ = date_range_split[date_range_split.notnull()].apply(lambda x: x[0])
        to_ = date_range_split[date_range_split.notnull()].apply(
            lambda x: x[1] if len(x) > 1 else None)
        to_.loc[to_ == 'Present'] = 'Jul 2020'
        from_ = pd.to_datetime(from_)
        to_ = pd.to_datetime(to_)

        return from_, to_

def main():
    education = pd.read_csv('education.csv')
    experiences = pd.read_csv('experiences.csv')
    cleaner = DataCleaner(education=education, experiences=experiences)
    cleaner.clean()


if __name__ == '__main__':
    main()
