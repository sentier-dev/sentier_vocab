#!/usr/bin/env bash
# This script generates all output data from the input files in this repository.
#
# If executed without arguments, it downloads the required external files and
# executes all generators:
#
#     $ scripts/generate.sh
#
# The `fetch` and `generate` sub-commands can be used to execute individual
# stages:
#
#     $ scripts/generate.sh fetch
#     $ scripts/generate.sh generate nace
set -euo pipefail

GENERATORS=(
    qudt
    combined_nomenclature
    envo
    model_terms
    open_energy_ontology
    custom_products
)

declare -A GENERATOR_ARGS
GENERATOR_ARGS=(
    [combined_nomenclature]=sentier_vocab/CN_2024.rdf
)

main() {
    [[ "$#" -eq 0 ]] && set -- all
    local cmd=$1; shift
    case "$cmd" in
    all) fetch; generate;;
    fetch) fetch "$@";;
    generate) generate "$@";;
    *) usage;;
    esac
}

usage() {
    echo >&2 <<EOF
Usage: $0 [CMD [ARG...]]

Commands:

    [all]
    fetch
    generate [MODULE...]
EOF
    return 1
}

fetch() {
    [[ "$#" -eq 0 ]] || usage
    echo == CN_2024.rdf.zip ==
    curl 'https://showvoc.op.europa.eu/semanticturkey/it.uniroma2.art.semanticturkey/st-core-services/Download/getFile?fileName=CN_2024.zip&ctx_project=ESTAT_Combined_Nomenclature%2C_2024_(CN_2024)&' \
        --compressed \
        -H 'Accept: application/json, text/plain, */*' \
        -H 'Accept-Encoding: gzip, deflate, br, zstd' \
        -H 'Connection: keep-alive' \
        -H 'Referer: https://showvoc.op.europa.eu/'\
        -H 'Cookie: translate.lang=en' \
        --output CN_2024.rdf.zip
    unzip -u CN_2024.rdf.zip
}

generate() {
    [[ "$#" -eq 0 ]] && set -- "${GENERATORS[@]}"
    local x
    for x; do
        echo "== $x =="
        python -m "sentier_vocab.$x" ${GENERATOR_ARGS[$x]-}
    done
}

main "$@"
