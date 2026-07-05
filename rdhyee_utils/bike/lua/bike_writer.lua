--[[
bike_writer.lua — a custom pandoc WRITER for the Bike outliner format.

This closes the loop named in Raymond's 2025-11-21 design journal
("Markdown → panflute → Bike XML → ??? → Bike.app"): pandoc can now EMIT
.bike directly, so any pandoc-readable format becomes Bike-importable:

    pandoc note.md -t path/to/bike_writer.lua -o note.bike
    pandoc -f gfm -t path/to/bike_writer.lua notes.md -o outline.bike

Serialization contract: the output matches Bike.app's own file style
byte-for-byte (2-space indents, alphabetical data-* attributes after id,
<p/> for empty paragraphs, &amp;/&lt;/&gt; text escaping) — the same
grammar that rdhyee_utils.bike.model reproduces and proves by round-trip.
A smoke test verifies BikeDoc.from_bytes(output).to_bytes() == output.

Block mapping (inverse of the bike.lua reader's "prose" mapping):

  Header level n     → heading row; subsequent blocks nest under it until
                       a Header of level <= n (outline-ization by level)
  Para / Plain       → body row
  BulletList         → unordered rows (or task rows when the item starts
                       with GFM task syntax / ☐ / ☒); item sub-blocks
                       become children
  OrderedList        → ordered rows
  CodeBlock          → one code row per line
  BlockQuote         → quote rows (nested blocks → children)
  HorizontalRule     → hr row
  Div class="note"   → note row(s)
  Table / RawBlock…  → flattened to body rows (Bike has no equivalent)

Inline mapping: Strong→<strong>, Emph→<em>, Code→<code>, Link→<a href>,
Strikeout→<s>, Span.mark→<mark>, everything else → its plain text.

Row ids: "rb1", "rb2", … (valid per the empirical id alphabet).  When
grafting into an existing document, rdhyee_utils.bike.mdimport re-generates
any colliding ids.
]]

-- ---------------------------------------------------------------------------
-- helpers
-- ---------------------------------------------------------------------------

local function escape_text(s)
  s = s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
  return s
end

local function escape_attr(s)
  s = escape_text(s):gsub('"', "&quot;")
  s = s:gsub("\n", "&#10;"):gsub("\t", "&#9;"):gsub("\r", "&#13;")
  return s
end

-- ---------------------------------------------------------------------------
-- inline rendering: pandoc Inlines → Bike <p> inner XML
-- ---------------------------------------------------------------------------

local render_inlines

local function wrap(tag, inlines, attrs)
  local a = ""
  if attrs then
    for _, kv in ipairs(attrs) do
      a = a .. string.format(' %s="%s"', kv[1], escape_attr(kv[2]))
    end
  end
  return string.format("<%s%s>%s</%s>", tag, a, render_inlines(inlines), tag)
end

render_inlines = function(inlines)
  local out = {}
  for _, el in ipairs(inlines) do
    if el.t == "Str" then
      table.insert(out, escape_text(el.text))
    elseif el.t == "Space" or el.t == "SoftBreak" then
      table.insert(out, " ")
    elseif el.t == "LineBreak" then
      table.insert(out, " ")
    elseif el.t == "Strong" then
      table.insert(out, wrap("strong", el.content))
    elseif el.t == "Emph" then
      table.insert(out, wrap("em", el.content))
    elseif el.t == "Strikeout" then
      table.insert(out, wrap("s", el.content))
    elseif el.t == "Code" then
      table.insert(out, "<code>" .. escape_text(el.text) .. "</code>")
    elseif el.t == "Link" then
      table.insert(out, wrap("a", el.content, { { "href", el.target } }))
    elseif el.t == "Span" then
      if el.classes:includes("mark") then
        table.insert(out, wrap("mark", el.content))
      else
        table.insert(out, render_inlines(el.content))
      end
    elseif el.t == "Quoted" then
      local q = el.quotetype == "SingleQuote" and "'" or '"'
      table.insert(out, q .. render_inlines(el.content) .. q)
    elseif el.t == "Math" then
      table.insert(out, escape_text(el.text))
    elseif el.t == "Note" then
      table.insert(out, "")  -- footnotes have no Bike equivalent; dropped
    elseif el.content ~= nil then
      table.insert(out, render_inlines(el.content))
    elseif el.text ~= nil then
      table.insert(out, escape_text(el.text))
    end
  end
  return table.concat(out)
end

-- ---------------------------------------------------------------------------
-- row construction
-- ---------------------------------------------------------------------------

local id_counter = 0
local function next_id()
  id_counter = id_counter + 1
  return "rb" .. id_counter
end

local function new_row(rtype, inner_xml)
  local row = { id = next_id(), rtype = rtype, inner = inner_xml or "", children = {} }
  return row
end

-- detect GFM task syntax at the start of a list item's inlines:
-- pandoc represents "- [ ] foo" as Str"☐"/checkbox chars or literal "[ ]"…
-- we normalize on the rendered text prefix.
local TASK_UNCHECKED = { "☐ ", "%[ %] " }
local TASK_CHECKED = { "☒ ", "%[x%] ", "%[X%] " }

local function detect_task(inner)
  for _, pat in ipairs(TASK_CHECKED) do
    local stripped, n = inner:gsub("^" .. pat, "", 1)
    if n > 0 then return "done", stripped end
  end
  for _, pat in ipairs(TASK_UNCHECKED) do
    local stripped, n = inner:gsub("^" .. pat, "", 1)
    if n > 0 then return "todo", stripped end
  end
  return nil, inner
end

-- ---------------------------------------------------------------------------
-- block rendering: pandoc Blocks → row forest
-- ---------------------------------------------------------------------------

local blocks_to_rows  -- forward decl

local function list_items_to_rows(items, rtype)
  local rows = {}
  for _, item in ipairs(items) do
    -- item is Blocks; first Plain/Para is the row text, rest are children
    local row = new_row(rtype, "")
    local rest = {}
    local got_text = false
    for _, b in ipairs(item) do
      if not got_text and (b.t == "Plain" or b.t == "Para") then
        row.inner = render_inlines(b.content)
        got_text = true
      else
        table.insert(rest, b)
      end
    end
    if rtype == "unordered" then
      local task_state, stripped = detect_task(row.inner)
      if task_state then
        row.rtype = "task"
        row.inner = stripped
        row.done = (task_state == "done")
      end
    end
    if #rest > 0 then
      row.children = blocks_to_rows(rest)
    end
    table.insert(rows, row)
  end
  return rows
end

blocks_to_rows = function(blocks)
  local rows = {}
  -- heading nesting: stack of {level=, row=}
  local stack = {}

  local function sink(row)
    -- attach to deepest open heading, else top level
    if #stack > 0 then
      table.insert(stack[#stack].row.children, row)
    else
      table.insert(rows, row)
    end
  end

  for _, b in ipairs(blocks) do
    if b.t == "Header" then
      local row = new_row("heading", render_inlines(b.content))
      while #stack > 0 and stack[#stack].level >= b.level do
        table.remove(stack)
      end
      sink(row)
      table.insert(stack, { level = b.level, row = row })
    elseif b.t == "Para" or b.t == "Plain" then
      sink(new_row("body", render_inlines(b.content)))
    elseif b.t == "BulletList" then
      for _, row in ipairs(list_items_to_rows(b.content, "unordered")) do
        sink(row)
      end
    elseif b.t == "OrderedList" then
      for _, row in ipairs(list_items_to_rows(b.content, "ordered")) do
        sink(row)
      end
    elseif b.t == "CodeBlock" then
      for line in (b.text .. "\n"):gmatch("(.-)\n") do
        sink(new_row("code", escape_text(line)))
      end
    elseif b.t == "BlockQuote" then
      -- quote paragraphs become quote rows; nested structure → children
      local inner_rows = blocks_to_rows(b.content)
      for _, row in ipairs(inner_rows) do
        if row.rtype == "body" then row.rtype = "quote" end
        sink(row)
      end
    elseif b.t == "HorizontalRule" then
      sink(new_row("hr", ""))
    elseif b.t == "Div" then
      local inner_rows = blocks_to_rows(b.content)
      if b.classes:includes("note") then
        for _, row in ipairs(inner_rows) do
          if row.rtype == "body" then row.rtype = "note" end
          sink(row)
        end
      else
        for _, row in ipairs(inner_rows) do sink(row) end
      end
    elseif b.t == "LineBlock" then
      for _, line in ipairs(b.content) do
        sink(new_row("body", render_inlines(line)))
      end
    elseif b.t == "Table" then
      -- Bike has no tables: flatten to a body row per cell-row
      sink(new_row("body", escape_text(pandoc.utils.stringify(b))))
    elseif b.t == "RawBlock" then
      sink(new_row("body", escape_text(b.text)))
    end
  end
  return rows
end

-- ---------------------------------------------------------------------------
-- serialization in Bike.app's exact style
-- ---------------------------------------------------------------------------

local function row_lines(row, indent, out)
  local pad = string.rep("  ", indent)
  local attrs = string.format(' id="%s"', escape_attr(row.id))
  if row.done then
    -- data-* attributes are alphabetical after id (data-done < data-type)
    attrs = attrs .. ' data-done="1970-01-01T00:00:00Z"'
  end
  if row.rtype ~= "body" then
    attrs = attrs .. string.format(' data-type="%s"', row.rtype)
  end
  table.insert(out, pad .. "<li" .. attrs .. ">")
  if row.inner ~= "" then
    table.insert(out, pad .. "  <p>" .. row.inner .. "</p>")
  else
    table.insert(out, pad .. "  <p/>")
  end
  if #row.children > 0 then
    table.insert(out, pad .. "  <ul>")
    for _, child in ipairs(row.children) do
      row_lines(child, indent + 2, out)
    end
    table.insert(out, pad .. "  </ul>")
  end
  table.insert(out, pad .. "</li>")
end

-- ---------------------------------------------------------------------------
-- the writer entry point
-- ---------------------------------------------------------------------------

function Writer(doc, opts)
  id_counter = 0
  local rows = blocks_to_rows(doc.blocks)
  local out = {
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<html xmlns="http://www.w3.org/1999/xhtml">',
    "  <head>",
    '    <meta charset="utf-8"/>',
    "  </head>",
    "  <body>",
    '    <ul id="rbRoot0">',
  }
  for _, row in ipairs(rows) do
    row_lines(row, 3, out)
  end
  table.insert(out, "    </ul>")
  table.insert(out, "  </body>")
  table.insert(out, "</html>")
  return table.concat(out, "\n") .. "\n"
end

function Template()
  return "$body$"
end
