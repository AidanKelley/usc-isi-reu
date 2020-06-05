from argparse import ArgumentParser
from somef import configuration, cli
import json
from rdflib import RDF, Graph, Literal, URIRef, Namespace
from rdflib.namespace import XSD

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


def process_somef(data):
    out = {}

    for key, value in data.items():
        if isinstance(value, list) or isinstance(value, tuple):
            if (len(value) > 0):
                out[key] = [obj["excerpt"] for obj in value]
        else:
            out[key] = value["excerpt"]

    return out


# loosely inspired by JSON-LD
# but this is mostly just a way to move the configuration out of the logic of the conversion
prefixes = {
    "schema": "https://schema.org/",
    "sd": "https://w3id.org/okn/o/sd#",
    "xsd": str(XSD)
}

software_rdf_table = {
    "description": {
        "@id": "sd:description",
        "@type": "xsd:string"
    },
    "citation": {
        "@id": "sd:citation",
        "@type": "xsd:string",
    },
    "installation": {
        "@id": "sd:hasInstallInstructions",
        "@type": "xsd:string"
    },
    "invocation": {
        "@id": "sd:hasExecutionCommand",
        "@type": "xsd:string"
    },
    "usage": {
        "@id": "sd:hasUsageNotes",
        "@type": "xsd:string"
    },
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
    "license": {
        "url": {
            "@id": "sd:license",
            "@type": "xsd:anyURI",
        }
    },
    # we skip over the "name" property
    "fullName": {
        "@id": "sd:name",
        "@type": "xsd:string"
    },
    # todo: Not sure about issue tracker
    # todo: forks_url has been ignored
    "topics": {
        "@id": "sd:keywords",
        "@type": "xsd:string",
    },
    # todo: readme_url is not used; maybe this should be used for description and what is current description can be "short description"?
}

software_source_rdf_table = {
    "codeRepository": {
        "@id": "sd:codeRepository",
        "@type": "xsd:anyURI"
    },
    "languages": {
        "@id": "sd:programmingLanguage",
        "@type": "xsd:string"
    },
    "description": {
        "@id": "sd:description",
        "@type": "xsd:string"
    },

}

author_from_name_table = {
    "@id": "schema:additionalName",
    "@type": "schema:Text"
}

author_person_rdf_table = {
    "owner": author_from_name_table
}

release_rdf_table = {
    "tag_name": {
        "@id": "sd:hasVersionId",
        "@type": "xsd:string"
    },
    "name": {
        "@id": "sd:name",
        "@type": "xsd:string"
    },
    # author_name is handled below as we create a new Person object
    "body": {
        "@id": "sd:description",
        "@type": "xsd:string"
    },
    # there are 4 different URLs, "tarball_url", "zipball_url", "html_url", and "url". I am only using html_url
    "html_url": {
        "@id": "sd:downloadUrl",
        "@type": "xsd:anyURI"
    },
    "dateCreated": {
        "@id": "sd:dateCreated",
        "@type": "xsd:dateTime"
    },
    "datePublished": {
        "@id": "sd:datePublished",
        "@type": "xsd:dateTime"
    }
}

g = Graph()

SD = Namespace("https://w3id.org/okn/o/sd#")
g.bind("sd", SD)

SCHEMA = Namespace("https://schema.org/")
g.bind("schema", SCHEMA)

XSD = Namespace("http://w3.org/2001/XMLSchema#")
g.bind("xsd", XSD)

OBJ = Namespace("https://example.org/objects/")


def decode_id(id):
    # split the id
    colon_index = id.index(":")
    id_prefix = id[0:colon_index]
    id_name = id[colon_index + 1:]

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
    # check if we are at the lowest level of the object
    if "@id" in mapping and "@type" in mapping:
        if isinstance(somef_data, list) or isinstance(somef_data, tuple):
            for value in somef_data:
                add_to_g((obj_id, mapping, value))
        else:
            add_to_g((obj_id, mapping, somef_data))
    else:
        for key, value in somef_data.items():
            if key in mapping:
                child_mapping = mapping[key]
                convert_from_somef(value, obj_id, child_mapping)


def add_author(name, author_type):
    # dict of url prefix and rdf type
    type_info = {
        "User": ["Person", SCHEMA.Person],
        "Organization": ["Organization", SCHEMA.Organization],
        "Bot": ["Robot", SCHEMA.Person]
    }

    # get the url_prefix and rdf type
    url_prefix, rdf_type = type_info[author_type]

    obj_id = OBJ[f"{url_prefix}/{name}"]
    if not (obj_id, None, None) in g:
        g.add((obj_id, RDF.type, rdf_type))
        convert_from_somef(name, obj_id, author_from_name_table)

    return obj_id


with open(in_file, "r") as in_handle:
    if is_csv:
        lines = set([line.split(",")[0] for index, line in enumerate(in_handle)
                     if index > 0 and len(line) > 2])
    else:
        lines = set([line[:-1] for line in in_handle if len(line) > 1])

    for index, repo in enumerate(lines):
        # get the data from SoMEF
        data = cli.cli_get_data(repo, somef_thresh)
        # with open(f"test_{index}.json", "w") as test_out:
        #     json.dump(data, test_out)

        processed = process_somef(data)

        # with open(f"test_{index}_processed.json", "w") as test_out:
        #     json.dump(processed, test_out)

        # Create the RDF object from the SoMEF output

        software_id = OBJ[f"Software/{processed['name']}/"]

        # create the author object
        author_id = add_author(processed["owner"], processed["ownerType"])

        # create a software source object
        software_source_id = OBJ[f"SoftwareSource/{processed['name']}/"]
        g.add((software_source_id, RDF.type, SD["SoftwareSource"]))
        convert_from_somef(processed, software_source_id, software_source_rdf_table)
        g.add((software_id, SD.hasSourceCode, software_source_id))

        # create and populate information about the software                                                                                                                                          g.add((software_id, RDF.type, SD["Software"]))
        g.add((software_id, SD.author, author_id))
        convert_from_somef(processed, software_id, software_rdf_table)

        # create the version information
        if 'releases' in processed:
            for release in processed['releases']:
                release_id = OBJ[f"SoftwareVersion/{processed['name']}/{release['tag_name']}"]
                assert((release_id, None, None) not in g)
                g.add((release_id, RDF.type, SD.SoftwareVersion))
                g.add((software_id, SD.hasVersion, release_id))

                # create author
                release_author_id = add_author(release["author_name"], release["authorType"])
                g.add((release_id, SD.author, release_author_id))

                # create rest of data
                convert_from_somef(release, release_id, release_rdf_table)


if out_file is not None:
    with open(out_file, "wb") as out_handle:
        out_handle.write(g.serialize(format='turtle'))
else:
    print(g.serialize(format='n3').decode("utf-8"))
