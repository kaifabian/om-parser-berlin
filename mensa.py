# -*- coding: utf-8 -*-
import sys
import os
import datetime
import time
import urllib2

import libxml2

from BeautifulSoup import *
from lxml.html import soupparser
from xml.sax.saxutils import escape, quoteattr

import pyopenmensa.feed

currUrl = "http://www.studentenwerk-berlin.de/print/mensen/speiseplan/{mensa}/woche.html"
nextUrl = "http://www.studentenwerk-berlin.de/print/mensen/speiseplan/{mensa}/naechste_woche.html"
metaUrl = "http://www.studentenwerk-berlin.de/mensen/mensen_cafeterien/{mensa}/index.html"

xsdLocation = "http://openmensa.org/open-mensa-v2.xsd"

mealsDisabled = [
]

metaDisabled = [
]

metaNames = {
    'fu1': 'fu1', #veggie no 1 van't hoff
    'fu2': 'mensa_fu_2', #otto-von-simson
    'fu_lankwitz': 'mensa_fu_lankwitz',
    'fu_assmannshauser': 'mensa_fu_zahnklinik',
    'fu_dueppel': 'mensa_fu_dueppel',
    'fu_cafeteria': 'cafeteria_koserstrasse', #koserstraße
    'fu_cafe_koenigin_luise': 'cafeteria_pharmazie_fu',
    'fu_cafe_vant_hoff': 'cafeteria_rechtswissenschaften_fu',
    'fu_cafe_ihne': 'cafeteria_am_osi',
    'fu_cafe_gary': 'cafeteria_wirtschaftswissenschaften_fu',

    'tu': 'mensa_tu_hardenbergstrasse', #hardenberg
    'tu_ackerstr': 'cafeteria_tu_ackerstrasse', # cafe!
    'tu_cafe_erp': 'cafeteria_ernst_reuter_platz', # ernst reuter
    'tu_cafe_skyline': 'cafeteria_tu_skyline',
    'tu_marchstr': 'cafeteria_tu_marchstraße',

    'hu_nord': 'mensa_nord',
    'hu_sued': 'mensa_sued',
    'hu_adlershof': 'cafeteria_oase_adlershof', # oase
    'hu_spandauer': 'mensa_hu_spandauer_strasse',

    'udk_jazzcafe': 'jazz_cafe', # cafeteria udk

    'htw_treskow': 'mensa_fhtw_treskowallee',
    'htw_wilhelminenhof': 'mensa_htw_wilhelminenhof',

    'hwr': 'mensa_fhw',

    'beuth': 'mensa_tfh', # luxemburger
    'beuth_kurfuersten': 'mensa_tfh_kurfuerstenstrasse',

    'hfm': 'mensa_hfm', # charlottenstr
    'hfm_cafeteria': 'cafeteria_hfm_schlossplatz', # cafe!

    'ashb': 'mensa_asfh', #hellersdorf

    'hfs': 'mensa_hfs', #schneller

    'khs': 'mensa_khs', #weißensee

    'khsb': 'mensa_kfh', # karlshorst

    'ehb': 'mensa_ehb', # teltower damm
}

noMealsRe = re.compile(r"(.*)(zur\s+zeit)(.*)(keine\s+speisepl.+ne)(.*)", re.IGNORECASE)

def dateStringToDate(datestr):
    y, m, d = map(int, datestr.split("-", 2))
    return datetime.date(y, m, d)

class ScraperError(Exception):
    pass

class ScraperStructureChangedError(ScraperError):
    pass

def urlGetContents(url):
    handle = urllib2.urlopen(url)
    content = handle.read().decode('utf-8')
    handle.close()

    return BeautifulSoup(content)

def scrapeUrl(url, builder, timeSpan=None):
    content = str(urlGetContents(url))

    if noMealsRe.search(content):
        if timeSpan:
            start, end = timeSpan
            oneDay = datetime.timedelta(days=1)
            current = start
            while current < end:
                builder.setDayClosed(current)
                current += oneDay
        return False

    xml = soupparser.fromstring(content)

    tables = xml.xpath("//table[contains(@class, 'mensa_week_table')]")

    if len(tables) != 1:
        raise ScraperStructureChangedError("Asserting 1 table, got {}".format(len(tables)))

    table = tables[0]

    dates = table.xpath("//thead/tr/th[contains(@class, 'mensa_week_head_col')]")
    if not len(dates) == 5:
        raise ScraperStructureChangedError("Asserting 5 dates, got {}".format(len(dates)))

    _dates = dict()
    dateRe = re.compile("(?P<weekName>[A-Za-z]+,?) (?P<day>[0-9]+)\.(?P<month>[0-9]+)\.(?P<year>[0-9]+)")

    for date in dates:
        if not date.text:
            continue

        dateText = dateRe.match(date.text)
        if not dateText:
            raise ScraperStructureChangedError("Could not parse date {}".format(repr(date.text)))

        day,month,year = map(lambda w: int(dateText.group(w)), ["day", "month", "year", ])
        year = year + 2000 if year < 1900 else year
        dateText = "{year:04}-{month:02}-{day:02}".format(day = day, month = month, year = year)

        parent = date.getparent()
        dateIndex = None
        for index,candidate in enumerate(parent.iterchildren()):
            if candidate == date:
                dateIndex = index

        if not dateIndex:
            raise ScraperStructureChangedError("Could not find index for {}".format(dateText))

        _dates[dateText] = (dateIndex, date)

    categories = map(lambda node: node.text, table.xpath("//tr/th[@class='mensa_week_speise_tag_title']"))
    _categories = dict()

    priceRe = re.compile("([0-9]+\.[0-9]+)")

    for date in sorted(_dates):
        dateIndex, dateNode = _dates[date]
        hasMeals = False

        dateAsDate = dateStringToDate(date)

        mealXpath = lambda elem, trIndex, tdIndex: elem.xpath("//tr[{tri}]/td[{tdi}]/p[contains(@class, 'mensa_speise')]".format(tri = trIndex, tdi = tdIndex))

        for categoryIndex,category in enumerate(categories):
            if len(mealXpath(table, categoryIndex + 1, dateIndex)) > 0:
                hasMeals = True

        if hasMeals:
            for categoryIndex,category in enumerate(categories):
                trIndex = categoryIndex + 1
                tdIndex = dateIndex
                meals = mealXpath(table, trIndex, tdIndex)

                if len(meals) > 0:
                    for meal in meals:
                        name = meal.xpath(".//strong")

                        priceNodes = meal.xpath(".//span[@class='mensa_preise']")

                        if len(name) != 1:
                            raise ScraperStructureChangedError("Could not find name for meal")
                        if len(priceNodes) != 1:
                            raise ScraperStructureChangedError("Could not find prices for meal")

                        _name = name[0]
                        name = name[0].text
                        if name:
                            roles = ("student", "employee", "other", )
                            priceList = priceRe.findall(" ".join(map(lambda p: p.text, priceNodes)))
                            prices = dict()
                            if len(priceList) > 1:
                                for index,price in enumerate(priceList):
                                    role = roles[index % len(roles)]
                                    prices[role] = pyopenmensa.feed.convertPrice(price)
                            elif priceList:
                                price = priceList[0]
                                for role in roles:
                                    prices[role] = pyopenmensa.feed.convertPrice(price)
                            builder.addMeal(dateAsDate, category, name.encode("utf-8"), prices=prices)
        else:
            builder.setDayClosed(dateAsDate)

    return True

def scrapeMensaByName(name, cacheTimeout = 15*60):
    cacheName = name.replace("/", "_").replace("\\", "_")
    cacheDir = os.path.join(os.path.dirname(__file__), "cache")
    cacheFile = "{name}.xml".format(name=cacheName)
    cachePath = os.path.join(cacheDir, cacheFile)

    if os.path.isfile(cachePath):
        now = time.time()
        cacheTime = os.path.getmtime(cachePath)
        age = now - cacheTime
        if age <= cacheTimeout:
            handle = open(cachePath, "rb")
            content = handle.read()
            handle.close()

            return content

    currentWeekUrl = currUrl.format(mensa=name)
    nextWeekUrl = nextUrl.format(mensa=name)

    lastMonday = datetime.date.today() + datetime.timedelta(days=-datetime.date.today().weekday())
    nextMonday = lastMonday + datetime.timedelta(weeks=1)
    aWorkingWeek = datetime.timedelta(days=5)
    currentWeek = (lastMonday, lastMonday + aWorkingWeek)
    nextWeek = (nextMonday, nextMonday + aWorkingWeek)

    try:
        if not metaNames[name]:
            meta_name = name
        else:
            meta_name = metaNames[name]
    except Exception, e:
        pass

    builder = pyopenmensa.feed.BaseBuilder()
    if not name in mealsDisabled:
        scrapeUrl(currentWeekUrl, builder, timeSpan=currentWeek)
        scrapeUrl(nextWeekUrl, builder, timeSpan=nextWeek)

    output = builder.toXMLFeed()

    if cacheTimeout > 0:
        handle = open(cachePath, "wb")
        handle.write(output)
        handle.close()

    return output

def canValidate():
    try:
        from lxml import etree
        from cStringIO import StringIO
    except ImportError, e:
        print e
        return False

    return True

def validate(xmldata, schema):
    try:
        from lxml import etree
        from cStringIO import StringIO
    except ImportError:
        return False

    scs = etree.parse(StringIO(schema))
    sch = etree.XMLSchema(scs)
    xml = etree.parse(StringIO(xmldata))

    try:
        sch.assertValid(xml)
        return True
    except etree.DocumentInvalid:
        print sch.error_log
        return False

if __name__ == "__main__" and "test" in sys.argv:
    doValidation = False
    if canValidate():
        doValidation = True

        try:
            import urllib2
            xsdh = urllib2.urlopen(xsdLocation)
            xsd = xsdh.read()
            xsdh.close()
        except:
            print "ERROR"
            doValidation = False

    if not doValidation:
        print "[ERR ] cannot validate!"

    for mensa_name in metaNames:
        print "---", "Testing", mensa_name, "---"
        try:
            mensa = scrapeMensaByName(mensa_name, cacheTimeout = -1)

            if doValidation:
                if not validate(mensa, xsd):
                    raise Exception("Validation Exception")

            f = open("test-{}.xml".format(mensa_name), "wb")
            f.write(mensa)
            f.close()
            print "SUCCESS"
        except Exception as e:
            print "FAILURE: {0!r}".format(e)
            if not isinstance(e, ScraperError):
                raise
