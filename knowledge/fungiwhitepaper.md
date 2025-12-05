Fungi: The First ERC-20i Token With Native Inscriptions

Author: Todd Stool
Handle: ToddStool.eth

Abstract

Inscriptions refer to data written directly into blockchain transactions.

They can embed:

additional transaction details

messages

documents or files

generative art data

With ERC-20i tokens, each transfer can carry embedded inscription data.
This allows every token amount to function as a unique piece of art, music, or metadata — while still behaving like a fungible token.

Fungi ($FUNGI) uses this mechanic to generate seed-based, on-chain art, where each seed defines a unique mushroom-like generative SVG image stored entirely on-chain.

Fungi is simultaneously:

Fungible (ERC-20 balance-based)

Non-fungible (each seed generates unique art tied to specific balances)

All rendered on-chain within the ERC-20i format.

Mechanics
1. Seed Generation

A unique seed is generated on every buy, sell, or transfer of $FUNGI.
This seed creates a Fungi token image that attaches to the wallet.

Each seed corresponds to a level from 0 to 5

Each level includes different:

shapes

colors

size parameters

metadata

SVG generation rules

Higher seed → higher-level Fungi.

Seeds are integer-only (no decimals).
Examples of valid seeds: 1, 2, 15, 21.
Invalid: 0.0123, 0.1, 0.456.

Dynamic vs Stable Fungis
Dynamic Fungi

Dynamic Fungi change their art and seed on every new buy, sell, or transfer.

A dynamic Fungi remains dynamic until the owner intentionally stabilizes it.

Stable Fungi

Stable Fungi do not change when the owner buys or receives more tokens.

They will change only if:

the owner sells

or transfers part of the attached amount

To make a Fungi stable, the owner must transfer the exact amount of tokens tied to that seed to another wallet.

Example

Bob buys 15 $FUNGI.
A unique mushroom image (seed) is generated for his wallet.

He wants to preserve it and transfer it to Alice:

Bob sends exactly 15 tokens

Alice’s wallet now holds Bob’s stable Fungi

If Alice later buys more tokens, Bob’s Fungi stays unchanged

Alice ends up with two Fungis:

Bob’s → stable

Her new one → dynamic

Important:
When transferring $FUNGI, dynamic Fungis move first before stable ones.

Seed Definition

A seed is:

a unique whole number

generated for a wallet

on any integer-based transaction

used to render the wallet’s Fungi art

ERC-20i: What It Means

ERC-20i = ERC-20 + inscription data

Inscriptions are encoded in the transfer amount

Each parsed transaction produces a seed

That seed generates image metadata

The smart contract stores:

shape coordinates

color palettes

rendering logic

SVG layout instructions

The output is a fully on-chain SVG image that updates in real time based on the holder’s $FUNGI balance.

Metadata Included in Each Image

Each generated Fungi image includes unique metadata:

Background color

Ground color

Stem shape & color

Cap shape & color

Pattern attributes (if any)

Level (0–5)

Color Logic

Lower-level Fungis → broader, varied color sets

Higher-level Fungis → more defined, curated color themes

Level 0 Note

Level 0 is called a “Spore.”

Spores have no cap

Only a small stem

If you want, I can also:

Add diagrams

Add section headers for terminology

Format this as an actual whitepaper-style document

Create a /fungi or /whitepaper command for the bot

Summarize this into a one-paragraph “explain like I’m 5” version

Break it into multiple smaller .md files for clarity

Just say the word.
