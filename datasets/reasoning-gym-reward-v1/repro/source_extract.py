"""Token-aware, AST-identity checked extraction reused from the project data tool.
No upstream method is modified. This is data preparation, not an analyzer.
"""
import ast
import hashlib
import io
import tokenize

def sha(data):
    return hashlib.sha256(data if isinstance(data,bytes) else data.encode()).hexdigest()

def extract_function(module_source, qualified_name):
    tree=ast.parse(module_source)
    parts=qualified_name.split(".")
    nodes=tree.body
    selected=None
    for part in parts:
        found=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==part]
        if len(found)!=1:raise ValueError("Ambiguous/missing original definition "+qualified_name)
        selected=found[0];nodes=selected.body
    if not isinstance(selected,(ast.FunctionDef,ast.AsyncFunctionDef)):raise ValueError("Expected function")
    start=min([selected.lineno]+[d.lineno for d in selected.decorator_list])
    lines=module_source.splitlines(keepends=True)
    # Indentation inside a multiline string is part of its VALUE. Strip only
    # the original definition's code prefix, leaving token interiors intact.
    protected=set();fstrings=[]
    fstart=getattr(tokenize,'FSTRING_START',None)
    fend=getattr(tokenize,'FSTRING_END',None)
    for token in tokenize.generate_tokens(io.StringIO(module_source).readline):
        if token.type==tokenize.STRING and token.end[0]>token.start[0]:
            protected.update(range(token.start[0]+1,token.end[0]+1))
        elif fstart is not None and token.type==fstart:
            fstrings.append(token.start[0])
        elif fend is not None and token.type==fend and fstrings:
            first=fstrings.pop()
            protected.update(range(first+1,token.end[0]+1))
    definition_line=lines[selected.lineno-1]
    prefix=definition_line[:len(definition_line)-len(definition_line.lstrip(' \t'))]
    source=''.join(line if number in protected or not line.startswith(prefix) else line[len(prefix):]
                   for number,line in enumerate(lines[start-1:selected.end_lineno],start))
    if not source.endswith("\n"):source+="\n"
    if ast.dump(ast.parse(source).body[0])!=ast.dump(selected):
        raise ValueError("Extracted function AST differs from original definition")
    return source,{"qualified_name":qualified_name,"start_line":start,"end_line":selected.end_lineno,
                   "source_sha256":sha(source),"module_sha256":sha(module_source),
                   "entry_async":isinstance(selected,ast.AsyncFunctionDef),"ast_identity_verified":True,
                   "transformation":"code-prefix dedent only; string interiors retained; whole AST identical"}
