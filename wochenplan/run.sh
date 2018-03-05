#!/usr/bin/env bash
set -e -u

tmpdir="$(mktemp -d)"

docfile="${tmpdir}/wochenplan_$(date +%F).doc"

if [[ -e "${docfile}" ]]; then
	echo "${docfile} exists, exiting"
	exit 1
fi

htmlfile="${docfile%.*}.html"

if [[ -e "${htmlfile}" ]]; then
	echo "${htmlfile} exists, exiting"
	exit 1
fi

curl http://htl-mensa.at/wochenplan.doc > "${docfile}"

libreoffice --headless --convert-to html:HTML --outdir "${tmpdir}" "${docfile}"

# remove first line, remove rogue <col>, trim duplicate style= attributes
sed -i -E '1d;/<col.*>/d;s|style=[^>]+style=[^>]+||g' "${htmlfile}"

./wochenplan.py "${htmlfile}"

rm -r "${tmpdir}"
