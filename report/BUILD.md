# Build the report

Run these commands from this directory with TeX Live and the ACM sigconf class installed.

~~~sh
pdflatex -interaction=nonstopmode -halt-on-error report.tex
bibtex report
pdflatex -interaction=nonstopmode -halt-on-error report.tex
pdflatex -interaction=nonstopmode -halt-on-error report.tex
~~~

The supplied report uses stock ACM sigconf and has nine main pages, including the AI usage statement, followed by one page of references. A different font installation or a change to the author fields can affect pagination.
