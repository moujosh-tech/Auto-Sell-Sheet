/*
  populate_sellsheets.jsx — WestPoint Hospitality sell sheet populator
  --------------------------------------------------------------------
  Run in Illustrator: File > Scripts > Other Script…

  Prompts for:
    1. The fetcher output folder (contains /pages, /images, manifest.json)
    2. The folder containing the two templates: x2_per_page.ai, x3_per_page.ai
    3. An output folder for the generated .ai files

  For each pages/page_NN.json it opens the matching template, fills frames by
  name, places images, and saves a copy as <Collection>_page_NN.ai.

  Frame naming convention (per slot N = 1..3, top to bottom):
    Name_N    text  – product title (used if no Logo_N image frame)
    Logo_N    any   – brand logo placeholder rectangle (SVG placed & fitted)
    Hero_N    any   – product photo placeholder rectangle (fitted, centered)
    Copy_N    text  – feature bullets (one per line, "•  " prefixed)
    Specs_N   text  – spec table body, TAB-separated columns, one row per line
                      (set tab stops in this frame's paragraph style)
    Colors_N  text  – "Available in White and *Ecru" line
  Page level:
    PageTitle text  – collection name (optional)
    PageNum   text  – "1 of 3" (optional)
*/

#target illustrator

(function () {

  // ---------- helpers ----------

  function readJSON(file) {
    file.encoding = "UTF-8";
    if (!file.open("r")) throw new Error("Cannot open " + file.fsName);
    var s = file.read();
    file.close();
    return eval("(" + s + ")"); // ExtendScript has no JSON.parse
  }

  function allLayers(container, out) {
    out = out || [];
    for (var i = 0; i < container.layers.length; i++) {
      out.push(container.layers[i]);
      allLayers(container.layers[i], out);
    }
    return out;
  }

  function unlockAll(doc) {
    // unlock & show every layer so frames can be edited and items placed;
    // returns saved states for restoreLayers()
    var states = [];
    var layers = allLayers(doc);
    for (var i = 0; i < layers.length; i++) {
      states.push({ layer: layers[i], locked: layers[i].locked,
                    visible: layers[i].visible });
      layers[i].locked = false;
      layers[i].visible = true;
    }
    // make sure the active layer is a real, editable layer
    doc.activeLayer = doc.layers[0];
    return states;
  }

  function restoreLayers(states) {
    for (var i = 0; i < states.length; i++) {
      try {
        states[i].layer.locked = states[i].locked;
        states[i].layer.visible = states[i].visible;
      } catch (e) {}
    }
  }

  function findItem(doc, name) {
    // search all page items by name, all layers, recursively
    try {
      var items = doc.pageItems;
      for (var i = 0; i < items.length; i++) {
        if (items[i].name === name) return items[i];
      }
    } catch (e) {}
    return null;
  }

  function setText(doc, name, contents) {
    var it = findItem(doc, name);
    if (it && it.typename === "TextFrame") {
      try { it.locked = false; } catch (e) {}
      it.contents = contents;
      return true;
    }
    return false;
  }

  function bounds(item) {
    var b = item.geometricBounds; // [left, top, right, bottom]
    return { l: b[0], t: b[1], r: b[2], b: b[3],
             w: b[2] - b[0], h: b[1] - b[3] };
  }

  function placeInto(doc, name, imgFile, fitMode) {
    // Places imgFile fitted inside the frame named `name`, centered.
    // fitMode "contain" (default) fits inside; "cover" fills & overflows.
    // SVGs are imported as vector groups (placedItems cannot link SVG).
    var frame = findItem(doc, name);
    if (!frame || !imgFile.exists) return false;
    try { frame.locked = false; } catch (e) {}
    var fb = bounds(frame);

    var placed;
    try {
      if (/\.svg$/i.test(imgFile.name)) {
        placed = doc.groupItems.createFromFile(imgFile);
      } else {
        placed = doc.placedItems.add();
        placed.file = imgFile;
      }
    } catch (e) {
      try { if (placed) placed.remove(); } catch (e2) {}
      return false;
    }

    var pb = bounds(placed);
    var scale = (fitMode === "cover")
      ? Math.max(fb.w / pb.w, fb.h / pb.h)
      : Math.min(fb.w / pb.w, fb.h / pb.h);
    placed.width = pb.w * scale;
    placed.height = pb.h * scale;

    var nb = bounds(placed);
    placed.position = [
      fb.l + (fb.w - nb.w) / 2,
      fb.t - (fb.h - nb.h) / 2
    ];

    // keep placed art on the same layer, just above the frame; hide the frame
    placed.move(frame, ElementPlacement.PLACEBEFORE);
    frame.hidden = true;
    return true;
  }

  function bulletsBlock(bullets) {
    // plain lines — the template's paragraph style supplies the bullets
    return bullets.join("\r");
  }

  function specsBlock(rows) {
    // TAB-separated: Size  Dimensions  GSM  Weight  Case Pack
    var lines = [];
    for (var i = 0; i < rows.length; i++) lines.push(rows[i].join("\t"));
    return lines.join("\r");
  }

  function sanitize(s) {
    return (s || "sellsheet").replace(/[^A-Za-z0-9_\- ]/g, "").replace(/\s+/g, "_");
  }

  // ---------- gather inputs ----------

  var dataFolder = Folder.selectDialog("Select the fetcher OUTPUT folder (contains pages/ and images/)");
  if (!dataFolder) return;
  var tplFolder = Folder.selectDialog("Select the folder containing x2_per_page.ai and x3_per_page.ai");
  if (!tplFolder) return;
  var outFolder = Folder.selectDialog("Select the output folder for generated .ai files");
  if (!outFolder) return;

  var pagesFolder = new Folder(dataFolder.fsName + "/pages");
  var imagesFolder = new Folder(dataFolder.fsName + "/images");
  var pageFiles = pagesFolder.getFiles("page_*.json");
  if (!pageFiles.length) { alert("No page_*.json files found in " + pagesFolder.fsName); return; }
  pageFiles.sort(function (a, b) { return a.name < b.name ? -1 : 1; });

  var templates = {
    x2: new File(tplFolder.fsName + "/x2_per_page.ai"),
    x3: new File(tplFolder.fsName + "/x3_per_page.ai")
  };
  if (!templates.x2.exists || !templates.x3.exists) {
    alert("Could not find x2_per_page.ai / x3_per_page.ai in " + tplFolder.fsName);
    return;
  }

  var report = [];

  // ---------- process pages ----------

  for (var p = 0; p < pageFiles.length; p++) {
    var data = readJSON(pageFiles[p]);
    var doc = app.open(templates[data.template]);
    var layerStates = unlockAll(doc);

    setText(doc, "PageTitle", data.collection || "");
    setText(doc, "PageNum", data.page + " of " + data.page_count);

    for (var s = 0; s < data.products.length; s++) {
      var n = s + 1;
      var prod = data.products[s];
      var miss = [];

      // brand logo (preferred) or text name
      var usedLogo = false;
      if (prod.logo) {
        usedLogo = placeInto(doc, "Logo_" + n,
          new File(imagesFolder.fsName + "/" + prod.logo), "contain");
      }
      if (!setText(doc, "Name_" + n, usedLogo ? "" : prod.name) && !usedLogo) {
        miss.push("Name_" + n);
      }

      if (prod.hero) {
        if (!placeInto(doc, "Hero_" + n,
            new File(imagesFolder.fsName + "/" + prod.hero), "cover")) {
          miss.push("Hero_" + n);
        }
      }

      if (!setText(doc, "Copy_" + n, bulletsBlock(prod.bullets || []))) miss.push("Copy_" + n);
      if (!setText(doc, "Specs_" + n, specsBlock(prod.spec_rows || []))) miss.push("Specs_" + n);
      if (prod.colors_line) {
        if (!setText(doc, "Colors_" + n, prod.colors_line)) miss.push("Colors_" + n);
      }

      if (miss.length) report.push(pageFiles[p].name + " / " + prod.handle +
        ": missing frames -> " + miss.join(", "));
    }

    // clear any unused trailing slots (e.g. 1 product on the x2 template)
    for (var e = data.products.length + 1; e <= 3; e++) {
      setText(doc, "Name_" + e, "");
      setText(doc, "Copy_" + e, "");
      setText(doc, "Specs_" + e, "");
      setText(doc, "Colors_" + e, "");
      var ef = findItem(doc, "Hero_" + e); if (ef) ef.hidden = true;
      var el = findItem(doc, "Logo_" + e); if (el) el.hidden = true;
    }

    restoreLayers(layerStates);

    var outName = sanitize(data.collection) + "_page_" +
      (data.page < 10 ? "0" : "") + data.page + ".ai";
    var outFile = new File(outFolder.fsName + "/" + outName);
    var opts = new IllustratorSaveOptions();
    doc.saveAs(outFile, opts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
  }

  alert("Done. " + pageFiles.length + " page(s) generated." +
    (report.length ? "\n\nWarnings:\n" + report.join("\n") : ""));

})();
