# -*- coding: utf-8 -*-
import sys,os
from BeautifulSoup import *
import libxml2,urllib2
from lxml.html import soupparser
import time

curr_url = "http://www.studentenwerk-berlin.de/print/mensen/speiseplan/{mensa}/woche.html"
next_url = "http://www.studentenwerk-berlin.de/print/mensen/speiseplan/{mensa}/naechste_woche.html"
meta_url = "http://www.studentenwerk-berlin.de/mensen/mensen_cafeterien/{mensa}/index.html"

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
	'tu_cafeteria': 'tu_cafeteria', # franklin
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

class ScraperError(Exception):
	pass

class ScraperStructureChangedError(ScraperError):
	pass

def getContents(url):
	handle = urllib2.urlopen(url)
	content = handle.read().decode('utf-8')
	handle.close()
	
	return BeautifulSoup(content)

def scrape(url):
	content = str(getContents(url))
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
	
	output = ""
	
	priceRe = re.compile("([0-9]+\.[0-9]+)")
	
	for date in sorted(_dates):
		dateIndex, dateNode = _dates[date]
		
		for categoryIndex,category in enumerate(categories):
			trIndex = categoryIndex + 1
			tdIndex = dateIndex
			meals = table.xpath(compFormat("//tr[{tri}]/td[{tdi}]/p[contains(@class, 'mensa_speise')]", tri = trIndex, tdi = tdIndex))
			
			if len(meals) > 0:
				output += compFormat(" <day date=\"{}\">\n", date)
				output += compFormat("  <category name=\"{}\">\n", category)
				
				for meal in meals:
					name = meal.xpath(".//strong")
					###zusatz = meal.xpath(".//a[@class='zusatz']")
					prices = meal.xpath(".//span[@class='mensa_preise']")
					
					if len(name) != 1:
						raise ScraperStructureChangedError("Could not find name for meal")
					###if len(zusatz) < 1:
					###	raise ScraperStructureChangedError("Could not find zusatz for meal")
					if len(prices) != 1:
						raise ScraperStructureChangedError("Could not find prices for meal")
					
					_name = name[0]
					name = name[0].text
					if name is None:
						name = ""
					prices = prices[0].text
					
					output += "   <meal>\n"
					output += compFormat("    <name>{name}</name>\n", name = name.encode("utf-8"))
					# output += "    <note />\n"
					
					for price in priceRe.findall(prices):
						output += compFormat("    <price>{}</price>\n", price)
					
					output += "   </meal>\n"
				
				output += "  </category>\n"
				output += " </day>\n"
	
	return output

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
	output += "  <om-proposed-v2:provider-info xmlns:om-proposed-v2=\"http://mirror.space-port.eu/~om/om-proposed-v2\">\n"
	output += "   <om-proposed-v2:name><![CDATA[Kai Fabian]]></om-proposed-v2:name>\n"
	output += "   <om-proposed-v2:contact type=\"email\"><![CDATA[kai@openmensa.org]]></om-proposed-v2:contact>\n"
	output += "  </om-proposed-v2:provider-info>\n"
	output += "\n"
	output += "  <om-proposed-v2:cafeteria-info xmlns:om-proposed-v2=\"http://mirror.space-port.eu/~om/om-proposed-v2\">\n"
	output += "   <om-proposed-v2:name><![CDATA[" + mensaname + "]]></om-proposed-v2:name>\n"
	output += "   <om-proposed-v2:street><![CDATA[" + strasse + "]]></om-proposed-v2:street>\n"
	output += "   <om-proposed-v2:zip>" + str(plz) + "</om-proposed-v2:zip>\n"
	output += "   <om-proposed-v2:city><![CDATA[" + ort + "]]></om-proposed-v2:city>\n"
	output += "   <om-proposed-v2:contact type=\"phone\"><![CDATA[" + telefon + "]]></om-proposed-v2:contact>\n"
	for url in urls:
		output += "   <om-proposed-v2:datasource type=\"text/html\" transport=\"http\"><![CDATA[" + url + "]]></om-proposed-v2:datasource>\n"
	output += " </om-proposed-v2:cafeteria-info>\n"
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

	output = \
"""<?xml version="1.0" encoding="UTF-8"?>
<cafeteria version="1.0"
			xmlns="http://openmensa.org/open-mensa-v1"
			xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
			xsi:schemaLocation="http://openmensa.org/open-mensa-v1 http://openmensa.org/open-mensa-v1.xsd">
"""

	url1 = compFormat(curr_url, mensa=name)
	url2 = compFormat(next_url, mensa=name)
	
	urls = [url1, url2, ]
	try:
		if not meta_names[name]:
			meta_name = name
		else:
			meta_name = meta_names[name]
		output += scrape_meta(meta_name, urls)
	except Exception, e:
		pass

	try:
		output += scrape(url1)
		output += scrape(url2)
		pass
	except Exception, e:
		raise e
		pass
	output += "</cafeteria>\n"

	if cacheTimeout > 0:
		handle = open(cachePath, "wb")
		handle.write(output)
		handle.close()

	return output

if __name__ == "__main__" and "test" in sys.argv:
	for mensa_name in meta_names:
		print "---", "Testing", mensa_name, "---"
		mensa = scrape_mensa(mensa_name, cacheTimeout = -1)
		
		f = open(compFormat("test-{}.xml", mensa_name), "wb")
		f.write(mensa)
		f.close()
