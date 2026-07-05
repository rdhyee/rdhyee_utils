--[[
bike.lua — a custom pandoc READER for the Bike outliner format.

This makes .bike a first-class pandoc source format:

    pandoc -f path/to/bike.lua overall.bike -t gfm -o overall.md
    pandoc -f path/to/bike.lua topic.bike -o topic.docx

Design (see BIKE_PANDOC_DESIGN.md):
  * Bike files are XHTML, but pandoc's HTML reader drops the semantics we
    need (li data-type / data-done don't survive; only ids do).  Instead we
    parse the outline structure line-by-line — Bike.app's serialization is
    strictly line-regular (one <li> per line, one <p> per line, 2-space
    indentation; verified by the byte-identical round-trip serializer in
    rdhyee_utils.bike.model) — and delegate ONLY the rich-text inline
    content of each <p> to pandoc's HTML reader.
  * Row-type mapping mirrors the "prose" style of rdhyee_utils.bike.mdrender:
      heading  → Header (level = 1 + number of heading ancestors, max 6)
      body     → Para; children of a body row become a nested BulletList
      task     → BulletList item with ☐ / ☒ marker (pandoc has no native
                 task-list AST node; GFM writers render these fine)
      ordered  → OrderedList (consecutive siblings merge)
      unordered→ BulletList (consecutive siblings merge)
      quote    → BlockQuote (consecutive siblings merge)
      code     → CodeBlock (consecutive childless siblings merge)
      hr       → HorizontalRule
      note     → Div with class "note"
      empty untyped rows (visual spacers) are skipped
  * Row ids are preserved: every heading carries its Bike row id as its
    identifier, so anchors survive into HTML/markdown output.

Limitations (MVP):
  * Assumes Bike.app serialization (line-regular).  Hand-mangled XML with
    multiple <li> on one line will not parse.
  * data-created/-modified timestamps are not carried into the AST.
]]

local BALLOT_BOX = utf8 and utf8.char(0x2610) or "\226\152\144"
local BALLOT_BOX_X = utf8 and utf8.char(0x2612) or "\226\152\146"

-- ---------------------------------------------------------------------------
-- stage 1: parse lines into a row tree
-- ---------------------------------------------------------------------------

local function parse_rows(input)
  local roots = {}
  local stack = {}        -- stack[d] = last row seen at depth d
  local current = nil     -- row whose <p> content we're waiting for / in
  local base_indent = nil

  for line in tostring(input):gmatch("[^\r\n]+") do
    local indent, li_attrs = line:match("^(%s*)<li([^>]*)>%s*$")
    if indent then
      local row = {
        id = li_attrs:match('id="([^"]*)"'),
        rtype = li_attrs:match('data%-type="([^"]*)"') or "body",
        done = li_attrs:match('data%-done="([^"]*)"') ~= nil,
        text_html = "",
        children = {},
      }
      if base_indent == nil then
        base_indent = #indent
      end
      local depth = math.floor((#indent - base_indent) / 4)  -- li step = 4
      if depth <= 0 then
        depth = 0
        table.insert(roots, row)
      else
        local parent = stack[depth - 1]
        if parent then
          table.insert(parent.children, row)
        else
          table.insert(roots, row)
        end
      end
      stack[depth] = row
      for d = depth + 1, #stack do stack[d] = nil end
      current = row
    elseif current then
      local p_inner = line:match("^%s*<p>(.*)</p>%s*$")
      if p_inner then
        current.text_html = p_inner
      elseif line:match("^%s*<p/>%s*$") then
        current.text_html = ""
      end
    end
  end
  return roots
end

-- ---------------------------------------------------------------------------
-- stage 2: inline content via pandoc's HTML reader
-- ---------------------------------------------------------------------------

local function inlines_of(row)
  if row.text_html == "" then
    return pandoc.Inlines({})
  end
  local doc = pandoc.read("<p>" .. row.text_html .. "</p>", "html")
  local first = doc.blocks[1]
  if first and (first.t == "Para" or first.t == "Plain") then
    return first.content
  end
  return pandoc.Inlines({ pandoc.Str(pandoc.utils.stringify(doc)) })
end

-- verbatim text of a row (for code blocks): strip tags, decode entities,
-- WITHOUT the HTML reader (which would collapse leading whitespace)
local function raw_text(row)
  local s = row.text_html:gsub("<[^>]->", "")
  s = s:gsub("&lt;", "<"):gsub("&gt;", ">"):gsub("&quot;", '"')
  s = s:gsub("&#(%d+);", function(n) return utf8.char(tonumber(n)) end)
  s = s:gsub("&amp;", "&")
  return s
end

local function is_spacer(row)
  return row.rtype == "body"
    and row.text_html == ""
    and #row.children == 0
end

-- ---------------------------------------------------------------------------
-- stage 3: row tree → pandoc blocks (the "prose" mapping)
-- ---------------------------------------------------------------------------

local emit_blocks  -- forward decl

-- render a row (and its subtree) as ONE list item (a Blocks value)
local function list_item(row, heading_level)
  local item = pandoc.Blocks({})
  local content = inlines_of(row)
  if row.rtype == "task" then
    local marker = row.done and BALLOT_BOX_X or BALLOT_BOX
    content:insert(1, pandoc.Space())
    content:insert(1, pandoc.Str(marker))
  end
  item:insert(pandoc.Plain(content))
  if #row.children > 0 then
    local sub = emit_list(row.children, heading_level)
    for _, b in ipairs(sub) do item:insert(b) end
  end
  return item
end

-- render sibling rows in LIST context → Blocks (lists only)
function emit_list(rows, heading_level)
  local blocks = pandoc.Blocks({})
  local i = 1
  while i <= #rows do
    local row = rows[i]
    if is_spacer(row) then
      i = i + 1
    elseif row.rtype == "ordered" then
      local items = {}
      while i <= #rows and rows[i].rtype == "ordered" do
        table.insert(items, list_item(rows[i], heading_level))
        i = i + 1
      end
      blocks:insert(pandoc.OrderedList(items))
    else
      local items = {}
      while i <= #rows and rows[i].rtype ~= "ordered"
            and not is_spacer(rows[i]) do
        table.insert(items, list_item(rows[i], heading_level))
        i = i + 1
      end
      blocks:insert(pandoc.BulletList(items))
    end
  end
  return blocks
end

-- render sibling rows in BLOCK context → Blocks
emit_blocks = function(rows, heading_level)
  local blocks = pandoc.Blocks({})
  local i = 1
  while i <= #rows do
    local row = rows[i]
    if is_spacer(row) then
      i = i + 1
    elseif row.rtype == "heading" then
      local level = math.min(heading_level, 6)
      blocks:insert(pandoc.Header(level, inlines_of(row), pandoc.Attr(row.id or "")))
      local sub = emit_blocks(row.children, heading_level + 1)
      for _, b in ipairs(sub) do blocks:insert(b) end
      i = i + 1
    elseif row.rtype == "code" and #row.children == 0 then
      local lines = {}
      while i <= #rows and rows[i].rtype == "code" and #rows[i].children == 0 do
        table.insert(lines, raw_text(rows[i]))
        i = i + 1
      end
      blocks:insert(pandoc.CodeBlock(table.concat(lines, "\n")))
    elseif row.rtype == "quote" then
      local qblocks = pandoc.Blocks({})
      while i <= #rows and rows[i].rtype == "quote" do
        qblocks:insert(pandoc.Para(inlines_of(rows[i])))
        local kids = rows[i].children
        if #kids > 0 then
          local sub = emit_list(kids, heading_level)
          for _, b in ipairs(sub) do qblocks:insert(b) end
        end
        i = i + 1
      end
      blocks:insert(pandoc.BlockQuote(qblocks))
    elseif row.rtype == "hr" then
      blocks:insert(pandoc.HorizontalRule())
      i = i + 1
    elseif row.rtype == "note" then
      local inner = pandoc.Blocks({ pandoc.Para(inlines_of(row)) })
      if #row.children > 0 then
        local sub = emit_list(row.children, heading_level)
        for _, b in ipairs(sub) do inner:insert(b) end
      end
      blocks:insert(pandoc.Div(inner, pandoc.Attr(row.id or "", { "note" })))
      i = i + 1
    elseif row.rtype == "unordered" or row.rtype == "ordered"
        or row.rtype == "task" then
      -- consecutive list-typed rows: hand the whole run to list context
      local run = {}
      while i <= #rows and (rows[i].rtype == "unordered"
            or rows[i].rtype == "ordered" or rows[i].rtype == "task") do
        table.insert(run, rows[i])
        i = i + 1
      end
      local sub = emit_list(run, heading_level)
      for _, b in ipairs(sub) do blocks:insert(b) end
    else -- body
      if row.text_html ~= "" then
        blocks:insert(pandoc.Para(inlines_of(row)))
      end
      if #row.children > 0 then
        local sub = emit_list(row.children, heading_level)
        for _, b in ipairs(sub) do blocks:insert(b) end
      end
      i = i + 1
    end
  end
  return blocks
end

-- ---------------------------------------------------------------------------
-- the reader entry point
-- ---------------------------------------------------------------------------

function Reader(input, opts)
  local roots = parse_rows(tostring(input))
  return pandoc.Pandoc(emit_blocks(roots, 1))
end
