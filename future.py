from BeautifulSoup import *
from lxml.html import soupparser
from xml.sax.saxutils import escape, quoteattr

def scrape_meta(name, urls):
    url = compFormat(meta_url, mensa = name)
    urls.append(url)

    content = str(urlGetContents(url))
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