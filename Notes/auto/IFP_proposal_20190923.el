(TeX-add-style-hook
 "IFP_proposal_20190923"
 (lambda ()
   (TeX-add-to-alist 'LaTeX-provided-package-options
                     '(("pdfpages" "final")))
   (add-to-list 'LaTeX-verbatim-environments-local "alltt")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "path")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "url")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "nolinkurl")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "hyperbaseurl")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "hyperimage")
   (add-to-list 'LaTeX-verbatim-macros-with-braces-local "hyperref")
   (add-to-list 'LaTeX-verbatim-macros-with-delims-local "path")
   (TeX-run-style-hooks
    "latex2e"
    "article"
    "art10"
    "amsmath"
    "amsfonts"
    "amsthm"
    "amssymb"
    "setspace"
    "fancyhdr"
    "lastpage"
    "extramarks"
    "chngpage"
    "soul"
    "color"
    "graphicx"
    "float"
    "wrapfig"
    "hanging"
    "rotating"
    "pdfpages"
    "breqn"
    "hyperref"
    "url"
    "natbib"
    "subcaption"
    "varioref"
    "epstopdf"
    "ifthen"
    "booktabs"
    "calc"
    "multicol"
    "multirow"
    "dcolumn"
    "tabularx"
    "verbatim"
    "longtable"
    "pdflscape"
    "palatino"
    "alltt"
    "bbm"
    "cancel"
    "hhline"
    "caption"
    "lscape"
    "geometry"
    "tablefootnote"
    "ulem"
    "tikz"
    "datenumber"
    "xifthen"
    "chronology")
   (TeX-add-symbols
    '("prob" 1)
    '("cov" 1)
    '("var" 1)
    '("expect" 1)
    '("norm" 1)
    "hmwkTitle"
    "hmwkDueDate"
    "hmwkAuthorName"
    "asgood"
    "betterthan"
    "indiff"
    "p"
    "hang"
    "gap"
    "unhang"
    "qeq")
   (LaTeX-add-bibliographies
    "../References/References.bib")
   (LaTeX-add-amsthm-newtheorems
    "theorem"
    "prediction"))
 :latex)

