/**
 * Descoberta de campos em tempo de execucao.
 *
 * O formulario nao tem seletores chumbados: cada pagina e inspecionada no
 * momento em que aparece. Isso sobrevive a mudancas de layout e funciona
 * mesmo quando o survey e renderizado dentro de um iframe.
 */

const ATTR = 'data-mcsa-id';

/**
 * Executa dentro do browser. Marca cada controle com um atributo estavel e
 * devolve um descritor serializavel para o lado Node.
 */
function collect(attr) {
  let seq = 0;
  const tag = (el) => {
    if (!el.getAttribute(attr)) el.setAttribute(attr, `mcsa-${seq++}`);
    return el.getAttribute(attr);
  };

  const visible = (el) => {
    if (!el || el.disabled) return false;
    const style = window.getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    // Radios costumam ser escondidos atras de um label estilizado; nesse caso
    // o label e que e visivel. Aceitamos o controle se ele ou seu label ocupam espaco.
    if (el.getClientRects().length > 0) return true;
    const labelled = el.labels && el.labels.length ? el.labels[0] : null;
    return !!(labelled && labelled.getClientRects().length > 0);
  };

  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();

  const textOfIds = (ids) =>
    clean(
      (ids || '')
        .split(/\s+/)
        .filter(Boolean)
        .map((id) => {
          const n = document.getElementById(id);
          return n ? n.textContent : '';
        })
        .join(' ')
    );

  /** Rotulo de um controle individual (a opcao, no caso de um radio). */
  const labelFor = (el) => {
    const byIds = textOfIds(el.getAttribute('aria-labelledby'));
    if (byIds) return byIds;
    const aria = clean(el.getAttribute('aria-label'));
    if (aria) return aria;
    if (el.labels && el.labels.length) {
      const t = clean(el.labels[0].textContent);
      if (t) return t;
    }
    const wrapping = el.closest('label');
    if (wrapping) {
      const t = clean(wrapping.textContent);
      if (t) return t;
    }
    // Texto imediatamente ao lado do input.
    const sib = el.nextElementSibling;
    if (sib) {
      const t = clean(sib.textContent);
      if (t && t.length < 120) return t;
    }
    const title = clean(el.getAttribute('title'));
    if (title) return title;
    return clean(el.value) || '';
  };

  /** Menor elemento que contem todos os nos informados. */
  const commonAncestor = (nodes) => {
    if (!nodes.length) return document.body;
    let anc = nodes[0].parentElement;
    while (anc && !nodes.every((n) => anc.contains(n))) anc = anc.parentElement;
    return anc || document.body;
  };

  /**
   * Enunciado da pergunta a que um grupo de controles pertence. Tenta as
   * fontes semanticas primeiro e so entao cai na heuristica de texto proximo.
   */
  const questionFor = (nodes) => {
    const first = nodes[0];

    const group = first.closest('[role="radiogroup"],[role="group"]');
    if (group) {
      const byIds = textOfIds(group.getAttribute('aria-labelledby'));
      if (byIds) return byIds;
      const aria = clean(group.getAttribute('aria-label'));
      if (aria) return aria;
    }

    const fs = first.closest('fieldset');
    if (fs) {
      const legend = fs.querySelector('legend');
      if (legend) {
        const t = clean(legend.textContent);
        if (t) return t;
      }
    }

    const byIds = textOfIds(first.getAttribute('aria-describedby'));
    if (byIds) return byIds;

    // Container do grupo, menos o texto das proprias opcoes.
    const anc = commonAncestor(nodes);
    const optionText = new Set(nodes.map((n) => clean(labelFor(n))).filter(Boolean));
    const scope = anc === document.body ? document.body : anc.parentElement || anc;

    const heading = [...scope.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,[class*="question"],[class*="pergunta"],[class*="Question"]')]
      .map((h) => clean(h.textContent))
      .filter((t) => t && t.length > 3 && !optionText.has(t))
      .pop();
    if (heading) return heading;

    // Ultimo recurso: primeiro bloco de texto do container que nao seja opcao.
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const t = clean(node.textContent);
      if (t && t.length > 3 && !optionText.has(t)) return t;
    }
    return '';
  };

  const controls = [];
  const seen = new Set();

  // --- Radios e checkboxes, agrupados por name (ou por container quando sem name).
  const boxes = [...document.querySelectorAll('input[type="radio"],input[type="checkbox"]')].filter(visible);
  const groups = new Map();
  for (const el of boxes) {
    const key = el.type === 'radio'
      ? `radio:${el.name || tag(commonAncestor([el]))}`
      : `check:${el.name || tag(el)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(el);
  }
  for (const [key, nodes] of groups) {
    const kind = key.startsWith('radio:') ? 'radio-group' : 'checkbox-group';
    controls.push({
      id: tag(commonAncestor(nodes)),
      kind,
      name: nodes[0].name || null,
      question: questionFor(nodes),
      required: nodes.some((n) => n.required || n.getAttribute('aria-required') === 'true'),
      options: nodes.map((n, index) => ({
        id: tag(n),
        index,
        label: labelFor(n),
        value: n.value,
        checked: n.checked,
      })),
    });
    nodes.forEach((n) => seen.add(n));
  }

  // --- ARIA radiogroups sem input nativo (divs com role=radio).
  for (const group of document.querySelectorAll('[role="radiogroup"]')) {
    const nodes = [...group.querySelectorAll('[role="radio"]')].filter(visible);
    if (!nodes.length) continue;
    controls.push({
      id: tag(group),
      kind: 'radio-group',
      name: null,
      question: questionFor(nodes),
      required: group.getAttribute('aria-required') === 'true',
      options: nodes.map((n, index) => ({
        id: tag(n),
        index,
        label: clean(n.textContent) || clean(n.getAttribute('aria-label')),
        value: n.getAttribute('data-value') || null,
        checked: n.getAttribute('aria-checked') === 'true',
      })),
    });
  }

  // --- Selects.
  for (const el of [...document.querySelectorAll('select')].filter(visible)) {
    controls.push({
      id: tag(el),
      kind: 'select',
      name: el.name || null,
      question: questionFor([el]),
      required: el.required,
      options: [...el.options].map((o, index) => ({
        index,
        label: clean(o.textContent),
        value: o.value,
        checked: o.selected,
      })),
    });
  }

  // --- Campos de texto livre.
  const textSel =
    'input[type="text"],input[type="number"],input[type="tel"],input[type="email"],input:not([type]),textarea';
  for (const el of [...document.querySelectorAll(textSel)].filter(visible)) {
    if (seen.has(el)) continue;
    // Um campo de texto tem rotulo proprio; a heuristica de grupo so entra
    // quando ele nao tem, senao todos os campos de um mesmo form acabam
    // herdando o primeiro texto do container.
    controls.push({
      id: tag(el),
      kind: el.tagName === 'TEXTAREA' ? 'textarea' : 'text',
      name: el.name || null,
      question: labelFor(el) || questionFor([el]),
      placeholder: clean(el.getAttribute('placeholder')),
      maxlength: el.getAttribute('maxlength') ? Number(el.getAttribute('maxlength')) : null,
      required: el.required,
      value: el.value,
    });
  }

  // --- Botoes de navegacao.
  const buttonSel = 'button,input[type="submit"],input[type="button"],a[role="button"],[role="button"]';
  const buttons = [...document.querySelectorAll(buttonSel)]
    .filter(visible)
    .map((el) => ({
      id: tag(el),
      label: clean(el.textContent) || clean(el.value) || clean(el.getAttribute('aria-label')),
      type: el.getAttribute('type') || el.tagName.toLowerCase(),
    }))
    .filter((b) => b.label);

  // --- Mensagens de erro/validacao ja presentes.
  const errorSel = '[role="alert"],[aria-invalid="true"],.error,.is-invalid,[class*="error"],[class*="erro"]';
  const errors = [...document.querySelectorAll(errorSel)]
    .filter((el) => el.getClientRects().length > 0)
    .map((el) => clean(el.textContent))
    .filter((t) => t && t.length < 300);

  return {
    url: location.href,
    title: document.title,
    heading: clean((document.querySelector('h1,h2') || {}).textContent),
    controls,
    buttons,
    errors: [...new Set(errors)],
  };
}

/**
 * Escolhe o frame que realmente contem o formulario. Plataformas de survey
 * costumam embutir o questionario num iframe, entao o frame principal pode
 * vir vazio.
 */
export async function findFormFrame(page) {
  let best = { frame: page.mainFrame(), snapshot: null, score: -1 };
  for (const frame of page.frames()) {
    let snapshot;
    try {
      snapshot = await frame.evaluate(collect, ATTR);
    } catch {
      continue; // frame cross-origin ou destruido durante a navegacao
    }
    const score = snapshot.controls.length * 10 + snapshot.buttons.length;
    if (score > best.score) best = { frame, snapshot, score };
  }
  if (!best.snapshot) best.snapshot = { url: page.url(), title: '', heading: '', controls: [], buttons: [], errors: [] };
  return best;
}

/** Snapshot da pagina atual: campos, botoes e erros visiveis. */
export async function snapshot(page) {
  const { frame, snapshot: snap } = await findFormFrame(page);
  return { frame, ...snap };
}

/** Localiza um elemento marcado durante a enumeracao. */
export function locate(frame, id) {
  return frame.locator(`[${ATTR}="${id}"]`);
}

/**
 * Impressao digital da pagina, usada para detectar se um clique em "proximo"
 * realmente avancou. Combina URL com o texto das perguntas visiveis.
 */
export function fingerprint(snap) {
  const questions = snap.controls.map((c) => `${c.kind}:${c.question}`).join('|');
  return `${snap.url}##${snap.heading}##${questions}`;
}

export { ATTR };
