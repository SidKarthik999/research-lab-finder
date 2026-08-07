// Builds DOM nodes via textContent/createTextNode instead of
// innerHTML + template literals + a hand-called escapeHtml() at every
// interpolation. That pattern was correct in the old app.js only because
// every interpolation remembered to escape -- Phase 5A introduces
// genuinely user-controlled strings (account display names, student
// profile text) where previously almost everything came from OpenAlex.
// Building nodes this way removes the whole class of bug instead of
// relying on remembering to guard each one.

// attrs: "class" sets className; "on<Event>" (a function) attaches a
// listener; "html" is an explicit escape hatch for a fixed, trusted
// string this codebase wrote itself -- never pass user-controlled data
// through it; everything else is set via setAttribute. Children may be
// strings, numbers, Nodes, null/false (skipped), or (nested) arrays of
// any of those, so `items.map(...)` can be passed straight through.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") {
      node.className = value;
    } else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "html") {
      node.innerHTML = value;
    } else if (value === true) {
      node.setAttribute(key, "");
    } else {
      node.setAttribute(key, value);
    }
  }

  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }

  return node;
}

export function clear(node) {
  node.replaceChildren();
}

export function mount(container, ...children) {
  clear(container);
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    container.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}
