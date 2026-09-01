/**
 * Politica de resposta: decide o que preencher em cada controle descoberto.
 *
 * As respostas vem do arquivo de configuracao do operador. Nada aqui inventa
 * conteudo por conta propria: se um campo nao tem regra correspondente, ele e
 * reportado como pendente para o operador preencher a mao no navegador.
 */

/** Extremos tipicos de escalas Likert em pt-BR, do mais positivo ao mais negativo. */
const POSITIVE = [
  'muito satisfeito', 'extremamente satisfeito', 'totalmente satisfeito', 'altamente satisfeito',
  'concordo totalmente', 'concordo plenamente', 'superou', 'excedeu',
  'excelente', 'otimo', 'muito bom', 'muito boa', 'sempre', 'com certeza',
  'definitivamente sim', 'muito provavel', 'certamente recomendaria', 'sim',
];

const NEGATIVE = [
  'muito insatisfeito', 'extremamente insatisfeito', 'totalmente insatisfeito',
  'discordo totalmente', 'discordo plenamente', 'ficou muito abaixo', 'abaixo',
  'pessimo', 'muito ruim', 'muito ma', 'nunca', 'de jeito nenhum',
  'definitivamente nao', 'muito improvavel', 'nao recomendaria', 'nao',
];

const norm = (s) =>
  (s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

/** Pontua um rotulo: >0 tende ao positivo, <0 ao negativo. */
function polarity(label) {
  const t = norm(label);
  if (!t) return 0;

  // Escalas numericas puras ("1".."5", "10") sao ordenadas pelo proprio numero.
  const asNumber = t.match(/^(\d{1,2})$/);
  if (asNumber) return Number(asNumber[1]);

  for (const [i, word] of POSITIVE.entries()) {
    if (t.includes(word)) return POSITIVE.length - i;
  }
  for (const [i, word] of NEGATIVE.entries()) {
    if (t.includes(word)) return -(NEGATIVE.length - i);
  }
  return 0;
}

/**
 * Descobre se a opcao mais positiva esta no inicio ou no fim da lista.
 * Retorna 'first', 'last' ou null quando os rotulos nao permitem decidir.
 */
export function detectDirection(options) {
  if (options.length < 2) return null;
  const first = polarity(options[0].label);
  const last = polarity(options[options.length - 1].label);
  if (first === last) return null;
  return first > last ? 'first' : 'last';
}

/**
 * Indice da opcao a escolher num grupo, conforme a politica configurada.
 * Devolve { index, reason } ou { index: null, reason } quando indeciso.
 */
export function chooseOption(control, policy, directionHint) {
  const options = control.options.filter((o) => o.label !== '' || o.value);
  if (!options.length) return { index: null, reason: 'grupo sem opcoes legiveis' };

  if (typeof policy === 'object' && policy !== null && Number.isInteger(policy.index)) {
    const idx = policy.index < 0 ? options.length + policy.index : policy.index;
    if (idx < 0 || idx >= options.length) {
      return { index: null, reason: `indice ${policy.index} fora da faixa (0..${options.length - 1})` };
    }
    return { index: idx, reason: `indice fixo ${policy.index}` };
  }

  if (policy === 'neutral') {
    return { index: Math.floor((options.length - 1) / 2), reason: 'ponto medio da escala' };
  }

  const wantPositive = policy === 'most-positive';
  let direction = directionHint === 'auto' || !directionHint ? detectDirection(options) : directionHint;
  let reason;

  if (!direction) {
    // Sem pistas nos rotulos: nao adivinha, devolve pendente.
    return {
      index: null,
      reason: 'nao foi possivel deduzir a orientacao da escala pelos rotulos; defina scaleDirection ou um override',
    };
  }
  reason = `escala com extremo positivo no ${direction === 'first' ? 'inicio' : 'fim'}`;

  const positiveEnd = direction === 'first' ? 0 : options.length - 1;
  const negativeEnd = direction === 'first' ? options.length - 1 : 0;
  return { index: wantPositive ? positiveEnd : negativeEnd, reason };
}

/** Primeiro override cujo padrao casa com o enunciado da pergunta. */
export function matchOverride(control, overrides = []) {
  const haystack = norm(`${control.question} ${control.placeholder || ''} ${control.name || ''}`);
  for (const rule of overrides) {
    if (!rule.match) continue;
    const pattern = norm(rule.match);
    const hit = rule.regex
      ? new RegExp(rule.match, 'i').test(`${control.question} ${control.placeholder || ''} ${control.name || ''}`)
      : haystack.includes(pattern);
    if (hit) return rule;
  }
  return null;
}

/**
 * Decide a acao para um controle. Formato de retorno:
 *   { action: 'select', index }        - marcar opcao de radio/select
 *   { action: 'type', text }           - digitar em campo de texto
 *   { action: 'skip', reason }         - deixar para o operador
 */
export function decide(control, config) {
  const answers = config.answers || {};
  const override = matchOverride(control, answers.overrides);

  if (override && override.skip) {
    return { action: 'skip', reason: `override pediu para pular: ${override.match}` };
  }

  switch (control.kind) {
    case 'radio-group':
    case 'checkbox-group': {
      if (override && override.option !== undefined) {
        const byLabel = control.options.findIndex((o) => norm(o.label).includes(norm(String(override.option))));
        if (byLabel >= 0) return { action: 'select', index: byLabel, reason: `override "${override.match}"` };
        if (Number.isInteger(override.option)) {
          return { action: 'select', index: override.option, reason: `override "${override.match}" (indice)` };
        }
        return { action: 'skip', reason: `override "${override.match}" nao casou com nenhuma opcao` };
      }
      const { index, reason } = chooseOption(control, answers.scalePolicy, answers.scaleDirection);
      if (index === null) return { action: 'skip', reason };
      return { action: 'select', index, reason };
    }

    case 'select': {
      if (override && override.option !== undefined) {
        const byLabel = control.options.findIndex((o) => norm(o.label).includes(norm(String(override.option))));
        if (byLabel >= 0) return { action: 'select', index: byLabel, reason: `override "${override.match}"` };
      }
      // Selects costumam ter um placeholder ("Selecione...") no indice 0.
      const real = control.options.filter((o, i) => !(i === 0 && (!o.value || /selec|escolha|choose/i.test(o.label))));
      if (!real.length) return { action: 'skip', reason: 'select sem opcoes reais' };
      const { index, reason } = chooseOption({ ...control, options: real }, answers.scalePolicy, answers.scaleDirection);
      if (index === null) return { action: 'skip', reason };
      const target = control.options.indexOf(real[index]);
      return { action: 'select', index: target, reason };
    }

    case 'text':
    case 'textarea': {
      if (override && override.text !== undefined) {
        return { action: 'type', text: String(override.text), reason: `override "${override.match}"` };
      }
      // Campos de cupom/nota fiscal: casa o rotulo com as chaves de `receipt`.
      // Vence a chave mais especifica, e o rotulo visivel tem prioridade sobre
      // o atributo name — senao um input name="cnpj" rotulado "Numero do
      // pedido" seria preenchido com o valor errado.
      const label = norm(`${control.question} ${control.placeholder || ''}`);
      const attr = norm(control.name || '');
      let best = null;
      for (const [key, value] of Object.entries(answers.receipt || {})) {
        const k = norm(key);
        if (!k) continue;
        let score;
        if (label.includes(k)) score = 2000 + k.length;
        else if (attr.includes(k)) score = 1000 + k.length;
        else continue;
        if (!best || score > best.score) best = { key, value, score };
      }
      if (best) {
        if (best.value === '' || best.value === null || best.value === undefined) {
          return { action: 'skip', reason: `campo "${best.key}" esta vazio na config` };
        }
        return { action: 'type', text: String(best.value), reason: `receipt.${best.key}` };
      }
      if (control.kind === 'textarea' && answers.comment) {
        return { action: 'type', text: String(answers.comment), reason: 'answers.comment' };
      }
      return { action: 'skip', reason: 'sem regra correspondente na config' };
    }

    default:
      return { action: 'skip', reason: `tipo de controle nao suportado: ${control.kind}` };
  }
}

export { norm, polarity };
