/**
 * Motor de preenchimento: aplica as respostas da config numa pagina e avanca.
 *
 * Uma execucao = uma pesquisa. Nao existe laco de repeticao, contador de
 * envios, agendamento ou paralelismo neste arquivo por decisao de projeto.
 */

import { snapshot, locate, fingerprint } from './enumerate.js';
import { decide } from './answers.js';

/** Rotulos que indicam avanco de pagina. */
const NEXT = /pr[oó]xim|avan[çc]ar|continuar|seguinte|next|continue|come[çc]ar|iniciar|start/i;
/** Rotulos que indicam envio definitivo. */
const SUBMIT = /enviar|finalizar|concluir|submit|finish|terminar/i;
/** Rotulos que nunca devem ser clicados automaticamente. */
const AVOID = /voltar|anterior|back|cancelar|sair|limpar|idioma|language|cookie|aceitar|privacidade/i;

/**
 * Classifica os botoes da pagina e devolve o melhor candidato para avancar.
 * `kind` e 'submit' quando o clique encerra a pesquisa.
 */
export function pickNavButton(buttons) {
  const usable = buttons.filter((b) => !AVOID.test(b.label));

  const submit = usable.find((b) => SUBMIT.test(b.label));
  const next = usable.find((b) => NEXT.test(b.label));

  if (next) return { ...next, kind: 'next' };
  if (submit) return { ...submit, kind: 'submit' };

  // Sem rotulo reconhecivel: um unico botao sobrando e provavelmente o avanco,
  // mas tratamos como envio para forcar a confirmacao humana.
  if (usable.length === 1) return { ...usable[0], kind: 'submit' };
  return null;
}

/** Aplica a decisao da config a um controle ja descoberto. */
async function apply(frame, control, plan) {
  if (control.kind === 'select') {
    const option = control.options[plan.index];
    const el = locate(frame, control.id);
    if (option.value) await el.selectOption({ value: option.value });
    else await el.selectOption({ index: plan.index });
    return option.label || option.value;
  }

  const option = control.options[plan.index];
  if (!option) throw new Error(`opcao ${plan.index} inexistente`);
  const el = locate(frame, option.id);

  // Radios estilizados costumam ficar por baixo de um label; o clique comum
  // falha e o fallback vai no label associado.
  try {
    await el.check({ timeout: 4000 });
  } catch {
    try {
      await el.click({ timeout: 4000, force: true });
    } catch {
      await frame.locator(`label[for="${await el.getAttribute('id')}"]`).click({ timeout: 4000 });
    }
  }
  return option.label || option.value;
}

/** Preenche todos os controles de uma pagina. Devolve o que foi feito. */
export async function fillPage(frame, snap, config, log) {
  const filled = [];
  const skipped = [];

  for (const control of snap.controls) {
    const plan = decide(control, config);

    if (plan.action === 'skip') {
      skipped.push({ question: control.question, reason: plan.reason, kind: control.kind });
      log(`  · pendente: ${short(control.question)} (${plan.reason})`);
      continue;
    }

    try {
      if (plan.action === 'type') {
        await locate(frame, control.id).fill(plan.text);
        filled.push({ question: control.question, answer: plan.text, reason: plan.reason });
        log(`  ✓ ${short(control.question)} = "${plan.text}"  [${plan.reason}]`);
      } else {
        const label = await apply(frame, control, plan);
        filled.push({ question: control.question, answer: label, reason: plan.reason });
        log(`  ✓ ${short(control.question)} = "${label}"  [${plan.reason}]`);
      }
    } catch (err) {
      skipped.push({ question: control.question, reason: `falha ao preencher: ${err.message}`, kind: control.kind });
      log(`  ✗ ${short(control.question)} — ${err.message}`);
    }
  }

  return { filled, skipped };
}

/**
 * Clica no botao e espera a pagina mudar de fato. Devolve o novo snapshot,
 * ou null se nada mudou (tipicamente erro de validacao).
 */
export async function advance(page, frame, button, before, timeout = 15000) {
  await locate(frame, button.id).click({ timeout: 10000 });

  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    await page.waitForTimeout(400);
    let snap;
    try {
      snap = await snapshot(page);
    } catch {
      continue; // navegacao em andamento
    }
    if (fingerprint(snap) !== before) return snap;
  }
  return null;
}

const short = (s) => {
  const t = (s || '(sem enunciado)').replace(/\s+/g, ' ').trim();
  return t.length > 60 ? `${t.slice(0, 59)}…` : t;
};

export { short };
