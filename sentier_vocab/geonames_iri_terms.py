import os
import zipfile
from urllib.request import urlretrieve

import polars as pl
import sentier_data_tools as sdt
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD
from skosify import infer

"""
The data for this was found at geonames' site, but it's much too large to put onto git.
For the data used to generate the dataframe for the entire world, look here:
384MB, unpacks to 1.6 GB https://download.geonames.org/export/dump/allCountries.zip
For the hierarchy dataframe, look here:
2MB, unpacks to 9MB https://download.geonames.org/export/dump/hierarchy.zip
For the altnernate names data, look here:
187MB, unpacks to 719MB https://download.geonames.org/export/dump/alternateNamesV2.zip
params:
world_path: location of allCountries.txt from allCountries.zip
hierarchy_path: location of hierarchy.txt from hierarchy.zip
altnames_path: location of alternateNamesV2.txt from alternateNamesV2.zip 
"""


def generateGeonameVocabulary(world_path: str, hierarchy_path: str, altnames_path: str):
    
    # ##  THIS PART FETCHES AND EXTRACTS.
    # temp_dir = os.path.join(os.curdir,"temp")
    # if not os.path.exists(temp_dir):
    #     os.mkdir(temp_dir)
    
    # hier_zip = os.path.realpath(os.path.join(temp_dir,"hierarchy.zip"))
    # hierarchy_path = os.path.realpath(os.path.join(temp_dir,"hierarchy.txt"))
    # hierarchy_url = "https://download.geonames.org/export/dump/hierarchy.zip"

    # world_zip = os.path.realpath(os.path.join(temp_dir,"allCountries.zip"))
    # world_path = os.path.realpath(os.path.join(temp_dir,"allCountries.txt"))
    # world_url = "https://download.geonames.org/export/dump/allCountries.zip"

    # altnames_zip = os.path.realpath(os.path.join(temp_dir,"alternateNamesv2.zip"))
    # altnames_path = os.path.realpath(os.path.join(temp_dir,"alternateNamesV2.txt"))
    # altnames_url = "https://download.geonames.org/export/dump/alternateNamesV2.zip"
    
    # urlretrieve(hierarchy_url,hier_zip)

    # urlretrieve(world_url,world_zip)
    
    # urlretrieve(altnames_url,altnames_zip)

    # with zipfile.ZipFile(hier_zip, 'r') as zip_ref:
    #     zip_ref.extractall(temp_dir)
    
    # with zipfile.ZipFile(world_zip, 'r') as zip_reff:
    #     zip_reff.extractall(temp_dir)
    
    # with zipfile.ZipFile(altnames_zip, 'r') as zip_reff:
    #     zip_reff.extractall(temp_dir)

    # ##FETCHING AND EXTRACTING COMPLETED

    GEOSPACES = "https://sws.geonames.org/"
    GN = Namespace("http://www.geonames.org/ontology#")

    all_schema = pl.Schema(
        {
            "geonameid": pl.Int64,
            "name": pl.String,
            "asciiname": pl.String,
            "alternatenames": pl.String,
            "latitude": pl.Float32,
            "longitude": pl.Float32,
            "feature_class": pl.String,
            "feature_code": pl.String,
            "country_code": pl.String,
            "cc2": pl.String,
            "admin1_code": pl.String,
            "admin2_code": pl.String,
            "admin3_code": pl.String,
            "admin4_code": pl.String,
            "population": pl.Int64,
            "elevation": pl.Int16,
            "dem": pl.Int64,
            "timezone": pl.String,
            "modification_date": pl.Date,
        }
    )

    world_frame = pl.scan_csv(
        source=world_path, separator="\t", schema=all_schema, has_header=False
    )

    ##In the SQL here you can actually expand or narrow what you're going to model.
    ##See more at https://download.geonames.org/export/dump/readme.txt, scroll down to "feature classes"
    ##to isolate only countries, use "where feature_code = 'PCLI'"
    
    hierarchy_schema = pl.Schema(
        {
            "parent":pl.Int64,
            "child":pl.Int64,
            "admin1_code":pl.String
            
        }
    )

    hierarchy = pl.scan_csv(
        hierarchy_path, separator="\t", schema=hierarchy_schema, has_header=False
    )

    alt_schema = pl.Schema(
        {
            "alternateNameId":pl.Int32,
            "geonameid":pl.Int64,
            "isolanguage":pl.String,
            "alternate_name":pl.String,
            "isPreferredName":pl.Int8,
            "isShortName":pl.Int8,
            "isColloquial":pl.Int8,
            "isHistoric":pl.Int8,
            "from":pl.String,
            "to":pl.String
        }
    )
    alternate_names = pl.scan_csv(altnames_path, schema=alt_schema, separator="\t")

    filtered_world = world_frame.sql(
        "select * from self where feature_code in ('PCLI', 'RGN', 'ADM1')"
    )
    filtered_alt_names = alternate_names.join(
        filtered_world, on="geonameid",how="full"
        ).select(alternate_names.collect_schema().names()).collect()

    filtered_world = filtered_world.collect()

    world = Graph()

    for item in tqdm(filtered_world.iter_rows(),total=filtered_world.height):
        uri = URIRef(GEOSPACES + str(item[0]))
        world.add((
            uri,
            SKOS.prefLabel,
            Literal(Literal(item[1]))
        ))
        world.add((
            uri,
            RDF.type,
            SKOS.Concept
        ))
        world.add((
            uri,
            GN.countryCode,
            Literal(item[8])
        ))
        children = hierarchy.sql(f"select * from self where parent = {item[0]}").collect()
        if len(children) > 0:
            for child in children.iter_rows():
                if not filtered_world.filter(pl.col('geonameid') == child[1]).is_empty():
                    world.add((
                        uri,
                        SKOS.narrower,
                        URIRef(GEOSPACES + str(child[1]))
                    ))
        specific_alt_names = filtered_alt_names.sql(f"select * from self where geonameid = {item[0]}")
        if specific_alt_names.height > 0:
            for alt in specific_alt_names.iter_rows():
                if alt[4] == 1:
                    world.add((
                        uri,
                        SKOS.prefLabel,
                        Literal(alt[3], lang=alt[2])
                    ))
                else:
                    world.add((
                        uri,
                        SKOS.altLabel,
                        Literal(alt[3], lang=alt[2])
                    ))

    infer.skos_hierarchical(world)
    world.serialize(destination='output/geonames-iri.ttl')