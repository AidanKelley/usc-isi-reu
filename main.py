from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("in_file", help="newline separated text file of github links")
parser.add_argument("-o", "--out_file", help="file to store the graph")
parser.add_argument("-t", "--threshold", help="threshold for SoMEF", default=0.9)
parser.add_argument("--csv", action="store_true")

args = parser.parse_args()

in_file = args.in_file
out_file = args.out_file
somef_thresh = float(args.threshold)
is_csv = args.csv


from somef import configuration, cli
import json
from rdflib import RDF, Graph, Literal, URIRef, Namespace 
from rdflib.namespace import XSD

def process_somef(data):
    out = {}

    for key, value in data.items():
        if isinstance(value, list) or isinstance(value, tuple):
            if(len(value) > 0):
                out[key] = [obj["excerpt"] for obj in value]
        else:
            out[key] = value["excerpt"]

    return out

# loosely inspired by JSON-LD
# but this is mostly just a way to move the configuration out of the logic of the conversion
prefixes =  {
    "schema":"https://schema.org/",
    "sd":"https://w3id.org/okn/o/sd#",
    "xsd":str(XSD)
}

software_rdf_table = {
    "description": {
        "@id":"sd:description",
        "@type":"xsd:string"
    },
    "installation": {
        "@id":"sd:hasInstallInstructions",
        "@type":"xsd:string"
    },
    "license": {
        "url": {
            "@id": "sd:license",
            "@type": "xsd:anyURI",
        }
    },
    "citation": {
        "@id": "sd:citation",
        "@type": "xsd:string",
    },
    # note: unsure where "invocation" should go
    "downloadUrl": {
        "@id": "sd:hasDownloadUrl",
        "@type": "xsd:anyURI",
    },
    "dateCreated": {
        "@id": "sd:dateCreated",
        "@type": "xsd:dateTime"
    },
    "dateModified": {
        "@id": "sd:dateModified",
        "@type": "xsd:dateTime"
    },
    "name": {
        "@id": "sd:name",
        "@type": "xsd:string"
    },
    #  issueTracker shows up in the crosswalk but not in schema.org or sd so it is ignored for now
    #  forksUrl has been ignored
    "topics": {
        "@id": "sd:keywords",
        "@type": "xsd:string",
    },
}

software_source_rdf_table = {
    "codeRepository": {
        "@id":"sd:codeRepository",
        "@type":"xsd:anyURI"
    },
    "languages": {
        "@id":"sd:programmingLanguage",
        "@type":"xsd:string"
    }
}

author_person_rdf_table = {
    "owner": {
        "@id":"schema:additionalName",
        "@type":"schema:Text"
    }
}

g = Graph()

SD = Namespace("https://w3id.org/okn/o/sd#");
g.bind("sd", SD)

SCHEMA = Namespace("https://schema.org/");
g.bind("schema", SCHEMA)

XSD = Namespace("http://w3.org/2001/XMLSchema#")
g.bind("xsd", XSD)

OBJ = Namespace("https://example.org/objects/");

def decode_id(id):
    # split the id
    colon_index = id.index(":")
    id_prefix = id[0:colon_index]
    id_name = id[colon_index+1 : ]

    if id_prefix in prefixes:
        namespace = Namespace(prefixes[id_prefix]) 
        return namespace[id_name]

    return URIRef(id)

def decode_value(value, value_type):
    if value_type == "id":
        return URIRef(value)
    else:
        return Literal(value, datatype=decode_id(value_type))

def add_to_g(triple):
    obj_id, mapping, value = triple
    g.add((obj_id, decode_id(mapping["@id"]), decode_value(value, mapping["@type"])))


def convert_from_somef(somef_data, obj_id, mapping):
    for key, value in somef_data.items():
        if key in mapping:
            child_mapping = mapping[key]
            # check if we are at the lowest level of the object
            if "@id" in child_mapping and "@type" in child_mapping:
                if isinstance(value, list) or isinstance(value, tuple):
                    for value_obj in value:
                        add_to_g((obj_id, child_mapping, value_obj))
                else:
                    add_to_g((obj_id, child_mapping, value))
            else:
                convert_from_somef(value, obj_id, child_mapping)

repos_checked = set()
with open(in_file, "r") as in_handle:
    if is_csv:
        lines = set([line.split(",")[0] for index, line in enumerate(in_handle)
                if index > 0 and len(line) > 2])
    else:
        lines = set([line[:-1] for line in in_handle if len(line) > 1])

    for repo in lines:
        ## get the data from SoMEF
        print(repo)
        data = cli.cli_get_data(repo, somef_thresh)
        processed = process_somef(data)
        
        ## Create the RDF object from the SoMEF output

        software_id = OBJ[f"Software/{processed['name']}/"]

        # create the author object
        author_id = OBJ[f"Person/{processed['owner']}"]
        if not (author_id, None, None) in g:
            g.add((author_id, RDF.type, SCHEMA.Person))
            convert_from_somef(processed, author_id, author_person_rdf_table)

        # create a software source object
        software_source_id = OBJ[f"SoftwareSource/{processed['name']}/"]
        g.add((software_source_id, RDF.type, SD["SoftwareSource"]))
        convert_from_somef(processed, software_source_id, software_source_rdf_table)
        g.add((software_id, SD.hasSourceCode, software_source_id))

        # create and populate information about the software
        g.add((software_id, RDF.type, SD["Software"]))
        g.add((software_id, SD.author, author_id))
        convert_from_somef(processed, software_id, software_rdf_table)

if out_file is not None:
    with open(out_file, "wb") as out_handle:
        out_handle.write(g.serialize(format='turtle'))
else: 
    print(g.serialize(format='n3').decode("utf-8"))
