#!/usr/bin/env bash
set -e -u

archive_dir="archive/"

tmpdir="$(mktemp -d)"

if [[ $# -eq 1 ]]; then
	if [[ ! -f "$1" ]]; then
		echo "bad input file: $1"
		exit 1
	fi

	echo "using existing .doc $1"
	docfile="$1"
else
	docfile="${tmpdir}/wochenplan.doc"

	curl http://htl-mensa.at/wochenplan.doc > "${docfile}"
fi

libreoffice --headless --convert-to html:HTML --outdir "${tmpdir}" "${docfile}"

htmlfile="$(basename "${docfile%.*}.html")"
# remove first line, remove rogue <col>, trim duplicate style= attributes
sed -i -E '1d;/<col.*>/d;s|style=[^>]+style=[^>]+||g' "${tmpdir}/${htmlfile}"

start_date="$(./tool.py --start-date "${tmpdir}/${htmlfile}")"

if [[ -f "${archive_dir}/${start_date}.doc" ]]; then
	echo "output file exists, exiting"
	exit
fi

cp "${docfile}" "${archive_dir}/${start_date}.doc"
cp "${tmpdir}/${htmlfile}" "${archive_dir}/${start_date}.html"

./tool.py -jo "${archive_dir}/${start_date}.json" "${tmpdir}/${htmlfile}"
./tool.py -t "${tmpdir}/${htmlfile}"

rm -r "${tmpdir}"
