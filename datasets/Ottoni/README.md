# Ottoni TSPWR datasets

These instances come from the traveling salesman problem with refueling (TSPWR)
work by Ottoni et al. The project uses their coordinates and fuel prices for TSP
and TSPWR experiments.

Reference: André L. C. Ottoni, Erivelton G. Nepomuceno, Marcos S. de Oliveira,
and Daniela C. R. de Oliveira. “Reinforcement learning for the traveling salesman
problem with refueling.” *Complex & Intelligent Systems* **8**, 2001–2015 (2022).
[https://doi.org/10.1007/s40747-021-00444-4](https://doi.org/10.1007/s40747-021-00444-4).
Published online in 2021; the volume publication year is 2022. This reference was
verified against the publisher's record; no thesis or bibliographic reference
was found in the current repository documentation.

Included instances:

- Bahia30D (`ciudades_Bahia30D.xlsx`)
- Minas24D (`Minas24D.xlsx`)
- Minas30D (`Minas30D.xlsx`)
- Minas57D (`Minas57D.xlsx`)

The project defaults use a maximum tank capacity of **150 L** and fuel consumption
expressed as **7 km/L**. These are experiment settings, not changes to the data.

## File provenance

Treat these as project-maintained workbook representations of the published
instances, not verified original downloads from the paper's authors. All four
workbooks identify Ivan Hernandez as their creator and last modifier in their
embedded metadata. The Minas workbooks entered repository history in commit
`908f307` (“Dataset last version”); the Bahia workbook has earlier history.
This supports project preparation of the workbooks, but the available history
does not establish the exact transcription/reconstruction process from published
tables or data. It does not prove that these Excel files were supplied by Ottoni
et al. This reorganization preserves every workbook byte unchanged.
