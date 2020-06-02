from somef import configuration, cli
import json

configuration.configure("3f40be2c42f0b0b87f0329a0c7a2c0f28870ee61")

data = cli.cli_get_data("https://github.com/AidanKelley/somef", 0.9)

print(json.dumps(data))

def process_somef(data):
    out = {}

    for key, value in data.items():
        if isinstance(value, list) or isinstance(value, tuple):
            if(len(value) > 0):
                out[key] = [obj["excerpt"] for obj in value]
        else:
            out[key] = value["excerpt"]

    return out

processed = process_somef(data)

print(json.dumps(processed))

somef_rdf_mapping_table = {
    "context": {
        "schema":"https://schema.org",
        "sd":"https://w3id.org/okn/o/sd",
        "xsd":"http://w3.org/2001/XMLSchema"
    },
    "values": {
        "description": {
            "id":"schema:description",
            "type":"schema:Text"
        },
        "installation": {
            "id":"sd:hasInstallInstructions",
            "type":"xsd:string"
        }
    }
}

context = somef_rdf_mapping_table["context"]
somef_rdf_mapping = somef_rdf_mapping_table["values"]

from rdflib import RDF, Graph, Literal, URIRef, Namespace 
# from rdflib.namespace import RDF

g = Graph()

SD = Namespace("https://w3id.org/okn/o/sd");
g.bind("sd", SD)

SCHEMA = Namespace("https://schema.org");
g.bind("schema", SCHEMA)

def decode_id(id):
    # split the id
    colon_index = id.index(":")
    id_prefix = id[0:colon_index]
    id_name = id[colon_index+1 : ]

    if id_prefix in context:
        namespace = Namespace(context[id_prefix]) 
        return namespace[id_name]

    return URIRef(id)

def decode_value(value, value_type):
    if value_type == "id":
        return URIRef(value)
    else:
        return Literal(value, datatype=decode_id(value_type))

def add_to_g(triple):
    obj_id, mapping, value = triple
    g.add((obj_id, decode_id(mapping["id"]), decode_value(value, mapping["type"])))


def convert_from_somef(somef_data, obj_id):
    for key, value in somef_data.items():
        if key in somef_rdf_mapping:
            mapping = somef_rdf_mapping[key]
            if isinstance(value, list) or isinstance(value, tuple):
                for value_obj in value:
                    add_to_g((obj_id, mapping, value_obj))
            else:
                add_to_g((obj_id, mapping, value_obj))


test = URIRef("http://example.org/test")

convert_from_somef(processed, test)

print(g)
print(g.serialize(format='n3').decode("utf-8"))
