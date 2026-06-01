import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS

from sentier_vocab import paths
from sentier_vocab.errors import SchemaValidationError
from sentier_vocab.rdf_mapping import concept_to_triples, schema_view

FLAT = str(paths.REPO_ROOT / "tests" / "fixtures" / "engine" / "flat.yaml")
SCHEME = "https://vocab.sentier.dev/flows/"
ONT = "https://vocab.sentier.dev/ontology/"
QUDT = "http://qudt.org/schema/qudt/"


def _triples(record):
    return set(concept_to_triples(record, "Thing", schema_view(FLAT), SCHEME))


def test_type_and_scheme_emitted():
    s = URIRef("https://vocab.sentier.dev/flows/X")
    t = _triples({"iri": str(s), "label": "X"})
    assert (s, RDF.type, URIRef(ONT + "Thing")) in t
    assert (s, SKOS.inScheme, URIRef(SCHEME)) in t


def test_lang_literal_and_plain_and_typed_and_ref_and_multivalued():
    s = URIRef("https://vocab.sentier.dev/flows/X")
    t = _triples(
        {
            "iri": str(s),
            "label": "Water",
            "code": "W",
            "ratio": 0.5,
            "unit": "http://qudt.org/vocab/unit/KiloGM",
            "tags": ["a", "b"],
        }
    )
    assert (s, SKOS.prefLabel, Literal("Water", lang="en")) in t
    assert (s, SKOS.notation, Literal("W")) in t
    assert (s, URIRef(ONT + "ratio"), Literal(0.5)) in t
    assert (s, URIRef(QUDT + "hasUnit"), URIRef("http://qudt.org/vocab/unit/KiloGM")) in t
    assert (s, URIRef(ONT + "tag"), Literal("a")) in t
    assert (s, URIRef(ONT + "tag"), Literal("b")) in t


def test_internal_slot_is_not_serialized():
    s = URIRef("https://vocab.sentier.dev/flows/X")
    t = _triples({"iri": str(s), "label": "X", "secret": "hidden"})
    assert all(o != Literal("hidden") for (_, _, o) in t)


def test_missing_slot_uri_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: https://vocab.sentier.dev/schemas/_bad\n"
        "name: bad\n"
        "prefixes: {linkml: 'https://w3id.org/linkml/', sentier: 'https://vocab.sentier.dev/'}\n"
        "default_prefix: sentier\ndefault_range: string\nimports: [linkml:types]\n"
        "classes:\n  T:\n    tree_root: true\n    attributes:\n"
        "      iri: {identifier: true, range: uriorcurie}\n"
        "      oops: {}\n"
    )
    with pytest.raises(SchemaValidationError):
        concept_to_triples(
            {"iri": "https://vocab.sentier.dev/flows/Y", "oops": "v"},
            "T",
            schema_view(str(bad)),
            SCHEME,
        )
