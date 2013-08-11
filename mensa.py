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

curr_url = "http://www.studentenwerk-berlin.de/print/mensen/speiseplan/{mensa}/woche.html"
next_url = "http://www.studentenwerk-berlin.de/print/mensen/speiseplan/{mensa}/naechste_woche.html"
meta_url = "http://www.studentenwerk-berlin.de/mensen/mensen_cafeterien/{mensa}/index.html"

xsd_location = "http://openmensa.org/open-mensa-v2.xsd"

meals_disabled = [
]

meta_disabled = [
]

meta_names = {
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
    'cafeteria_tu': 'cafeteria_tu', # franklin
    'tu_ackerstr': 'cafeteria_tu_ackerstrasse', # cafe!
    'tu_cafe_erp': 'cafeteria_ernst_reuter_platz', # ernst reuter
    'tu_cafe_skyline': 'cafeteria_tu_skyline',
    # fehlt speiseplan:
    # - cafeteria_tu
    # - cafeteria_tu_hauptgebaeude

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

def compFormat(instr, *args, **kwargs):
    if hasattr(instr, "format"):
        return instr.format(*args, **kwargs)

    slices = instr.split("{}")
    instr = ""
    if len(slices) - 1 == len(args):
        for i in range(0, len(args)):
            instr += slices[i]
            instr += str(args[i])
        instr += slices[-1]

    for i in range(0, len(args)):
        instr = instr.replace("{" + str(i) + "}", str(args[i]))

    for name in kwargs:
        value = str(kwargs[name])
        instr = instr.replace("{" + name + "}", value)
        x = re.compile("{" + re.escape(name) + ":(?P<pad>.)(?P<length>[0-9]+)}")
        y = set(x.findall(instr))
        if len(y) > 0:
            for pad, length in y:
                length = int(length)
                padded = (pad * (length - len(value))) + value
                instr = instr.replace("{" + name + ":" + pad + str(length) + "}", padded)

    return instr

def dateStringToDate(datestr):
    y, m, d = map(int, datestr.split("-", 2))
    return datetime.date(y, m, d)

class ScraperError(Exception):
    pass

class ScraperStructureChangedError(ScraperError):
    pass

def getContents(url):
    handle = urllib2.urlopen(url)
    content = handle.read().decode('utf-8')
    handle.close()

    return BeautifulSoup(content)

def scrape(url, builder, timeSpan=None):
    content = str(getContents(url))

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
        raise ScraperStructureChangedError(compFormat("Asserting 1 table, got {}", len(tables)))

    table = tables[0]

    dates = table.xpath("//thead/tr/th[contains(@class, 'mensa_week_head_col')]")
    if not len(dates) == 5:
        raise ScraperStructureChangedError(compFormat("Asserting 5 dates, got {}", len(dates)))

    _dates = dict()
    dateRe = re.compile("(?P<weekName>[A-Za-z]+,?) (?P<day>[0-9]+)\.(?P<month>[0-9]+)\.(?P<year>[0-9]+)")

    for date in dates:
        if not date.text:
            continue

        dateText = dateRe.match(date.text)
        if not dateText:
            raise ScraperStructureChangedError(compFormat("Could not parse date {}", repr(date.text)))

        day,month,year = map(lambda w: int(dateText.group(w)), ["day", "month", "year", ])
        year = year + 2000 if year < 1900 else year
        dateText = compFormat("{year:04}-{month:02}-{day:02}", day = day, month = month, year = year)

        parent = date.getparent()
        dateIndex = None
        for index,candidate in enumerate(parent.iterchildren()):
            if candidate == date:
                dateIndex = index

        if not dateIndex:
            raise ScraperStructureChangedError(compFormat("Could not find index for {}", dateText))

        _dates[dateText] = (dateIndex, date)

    categories = map(lambda node: node.text, table.xpath("//tr/th[@class='mensa_week_speise_tag_title']"))
    _categories = dict()

    priceRe = re.compile("([0-9]+\.[0-9]+)")

    for date in sorted(_dates):
        dateIndex, dateNode = _dates[date]
        hasMeals = False

        dateAsDate = dateStringToDate(date)

        mealXpath = lambda elem, trIndex, tdIndex: elem.xpath(compFormat("//tr[{tri}]/td[{tdi}]/p[contains(@class, 'mensa_speise')]", tri = trIndex, tdi = tdIndex))

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

def scrape_meta(name, urls):
    url = compFormat(meta_url, mensa = name)
    urls.append(url)

    content = str(getContents(url))
    xml = soupparser.fromstring(content)

    mensaname = xml.xpath('//div[contains(@class, "einrichtung")]/h1/text()')
    adresse = xml.xpath('//p[contains(@class, "adresse")]/text()')
    telefon = xml.xpath('//p[contains(@class, "telefon")]/text()')
    if len(mensaname) < 1:
        raise ScraperStructureChangedError("Name not found in meta")
    if len(adresse) < 2:
        raise ScraperStructureChangedError("Address not found in meta")
    if len(telefon) < 1:
        raise ScraperStructureChangedError("Telephone not found in meta")

    mensaname = mensaname[0].strip().encode("utf-8")
    strasse = adresse[0].strip().encode("utf-8")
    plzort = adresse[1].strip()
    plz,ort = plzort.split(" ", 1)
    plz = int(plz)
    ort = ort.encode("utf-8")
    telefon = telefon[0].strip().encode("utf-8")

    output = " <!--\n"
    output += "   <om-proposed:info xmlns:om-proposed=\"http://mirror.space-port.eu/~om/om-proposed\">\n"
    output += "    <om-proposed:name><![CDATA[" + mensaname + "]]></om-proposed:name>\n"
    output += "    <om-proposed:street><![CDATA[" + strasse + "]]></om-proposed:street>\n"
    output += "    <om-proposed:zip>" + str(plz) + "</om-proposed:zip>\n"
    output += "    <om-proposed:city><![CDATA[" + ort + "]]></om-proposed:city>\n"
    output += "    <om-proposed:contact type=\"phone\"><![CDATA[" + telefon + "]]></om-proposed:contact>\n"
    output += "  </om-proposed:info>\n"
    output += " -->\n\n"

    return output

def scrape_mensa(name, cacheTimeout = 15*60):
    cacheName = name.replace("/", "_").replace("\\", "_")
    cacheDir = os.path.join(os.path.dirname(__file__), "cache")
    cacheFile = compFormat("{name}.xml", name=cacheName)
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

    currentWeekUrl = compFormat(curr_url, mensa=name)
    nextWeekUrl = compFormat(next_url, mensa=name)

    lastMonday = datetime.date.today() + datetime.timedelta(days=-datetime.date.today().weekday())
    nextMonday = lastMonday + datetime.timedelta(weeks=1)
    aWorkingWeek = datetime.timedelta(days=5)
    currentWeek = (lastMonday, lastMonday + aWorkingWeek)
    nextWeek = (nextMonday, nextMonday + aWorkingWeek)

    try:
        if not meta_names[name]:
            meta_name = name
        else:
            meta_name = meta_names[name]
    except Exception, e:
        pass

    builder = pyopenmensa.feed.BaseBuilder()
    if not name in meals_disabled:
        scrape(currentWeekUrl, builder, timeSpan=currentWeek)
        scrape(nextWeekUrl, builder, timeSpan=nextWeek)

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
            xsdh = urllib2.urlopen(xsd_location)
            xsd = xsdh.read()
            xsdh.close()
        except:
            print "ERROR"
            doValidation = False

    if not doValidation:
        print "[ERR ] cannot validate!"

    for mensa_name in meta_names:
        print "---", "Testing", mensa_name, "---"
        try:
            mensa = scrape_mensa(mensa_name, cacheTimeout = -1)

            if doValidation:
                if not validate(mensa, xsd):
                    raise Exception("Validation Exception")

            f = open(compFormat("test-{}.xml", mensa_name), "wb")
            f.write(mensa)
            f.close()
            print "SUCCESS"
        except Exception as e:
            print "FAILURE: {0!r}".format(e)
            if not isinstance(e, ScraperError):
                raise
