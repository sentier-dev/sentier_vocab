"""Schema-driven RDF serialization.

Turns a validated data record into RDF triples by reading each LinkML slot's
``slot_uri`` and ``range`` from the schema. Adding a data type never requires
touching this module.
"""

from functools import lru_cache

from linkml_runtime import SchemaView
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from sentier_vocab.errors import SchemaValidationError

_NUMERIC = {"float", "double", "decimal", "integer"}


@lru_cache(maxsize=None)
def schema_view(schema_path: str) -> SchemaView:
    """Cached SchemaView for a schema file path."""
    return SchemaView(schema_path)


def _ann(element, key):
    anns = getattr(element, "annotations", None) or {}
    if key in anns:
        a = anns[key]
        return getattr(a, "value", a)
    return None


def _expand(sv: SchemaView, curie: str) -> str:
    if curie is None:
        return None
    if "://" in curie:
        return curie
    return str(sv.namespaces().uri_for(curie))


def _literal_for(value, slot, rng):
    if rng in _NUMERIC:
        return Literal(value)  # rdflib infers xsd type from the Python value
    if rng == "boolean":
        return Literal(bool(value))
    if rng == "date":
        return Literal(str(value), datatype=XSD.date)
    if _ann(slot, "lang_tagged"):
        return Literal(str(value), lang="en")
    return Literal(str(value))


def _object_triples(record, class_name, sv, subject):
    """rdf:type + slot triples for a node (no inScheme). Used for top-level and inlined nodes."""
    triples = []
    cls = sv.get_class(class_name)
    if cls.class_uri:
        triples.append((subject, RDF.type, URIRef(_expand(sv, cls.class_uri))))

    for slot_name in sv.class_slots(class_name):
        slot = sv.induced_slot(slot_name, class_name)
        if slot.identifier or _ann(slot, "internal"):
            continue
        value = record.get(slot_name)
        if value is None:
            continue
        if not slot.slot_uri:
            raise SchemaValidationError(
                f"slot '{slot_name}' on class '{class_name}' has no slot_uri "
                f"and is not annotated internal: true"
            )
        pred = URIRef(_expand(sv, slot.slot_uri))
        items = value if slot.multivalued else [value]
        for item in items:
            triples.extend(_slot_value_triples(subject, pred, item, slot, sv))
    return triples


def _slot_value_triples(subject, pred, item, slot, sv):
    rng = slot.range
    if rng in sv.all_classes() and (slot.inlined or slot.inlined_as_list):
        child = _mint_child_iri(subject, slot, item, sv)
        return [(subject, pred, child), *_object_triples(item, rng, sv, child)]
    if rng in sv.all_classes() or rng in ("uriorcurie", "uri"):
        return [(subject, pred, URIRef(item))]
    if rng in sv.all_enums():
        return [(subject, pred, Literal(str(item)))]
    return [(subject, pred, _literal_for(item, slot, rng))]


def _mint_child_iri(parent, slot, item, sv):
    """Deterministic IRI for an inlined child node.

    Uses the slot's ``iri_key`` annotation (a sub-slot whose value's trailing id
    names the child) and optional ``iri_suffix`` annotation (a sub-slot appended
    for disambiguation). Falls back to the slot name only if no key is given.
    """
    from sentier_vocab.iris import identifier_from

    key_slot = _ann(slot, "iri_key")
    suffix_slot = _ann(slot, "iri_suffix")
    if key_slot and item.get(key_slot) is not None:
        slug = identifier_from(item[key_slot])
        if suffix_slot and item.get(suffix_slot) is not None:
            slug = f"{slug}-{item[suffix_slot]}"
    else:
        slug = "node"
    return URIRef(f"{str(parent).rstrip('/')}/{slot.name}/{slug}")


def concept_to_triples(record, class_name, sv, scheme):
    """Top-level: rdf:type + skos:inScheme + all slot triples for one record."""
    subject = URIRef(record["iri"])
    triples = _object_triples(record, class_name, sv, subject)
    triples.append((subject, SKOS.inScheme, URIRef(scheme)))
    return triples
