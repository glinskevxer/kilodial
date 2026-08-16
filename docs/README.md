# kilodial documentation

Generated for kilodial 1.0.0. Do not edit by hand.
Rebuild with: python -m kilodial.tools.build_index

Everything in this directory is generated from the code, so nothing in it can describe a version of this package that never existed.

## Documents

### [Command reference](commands.md)

Every command in the tree, its arguments and its options, read off the command tree itself.

    python -m kilodial.tools.build_docs

### [Schema](schema.sql)

The whole book as one flat file, built by running every migration into an empty database and asking sqlite what came out.

    python -m kilodial.tools.schema_dump

### [Glossary](glossary.md)

The domain's vocabulary, taken from the classes that define it. Start here if a word in the code does not mean what it means elsewhere.

    python -m kilodial.tools.build_glossary

### [Layers](layers.md)

Which package may import which, and the direction the whole thing points in.

    python -m kilodial.tools.check_layers --write

## Rebuilding all of them

    python -m kilodial.tools.gates

checks every one of these is current, along with the rest of the gates. It does not rewrite them; each tool above does that.
