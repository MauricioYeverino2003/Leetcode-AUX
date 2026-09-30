/**
 * The data-sharing notice.
 *
 * The backend runs on OpenAI's data-sharing program (free daily tokens in
 * exchange for letting OpenAI train on the traffic). Their Content Sharing
 * Agreement obliges us to notify end users and collect their consent, and to
 * hand OpenAI a copy of that notice on request. This component IS that notice,
 * so its wording lives here and nowhere else, and git history is its record.
 *
 * Consent is implied: it is shown in the empty chat before the first message,
 * and sending a message is the agreeing act. It is also reachable at any time
 * from the Privacy link in the header. See docs/design-choices.md.
 *
 * If the backend's provider changes, this text must change with it —
 * Anthropic's API does not train on requests by default, so the second
 * paragraph would become untrue.
 */
export function Notice({ title = "Before you send your first message" }: { title?: string }) {
  return (
    <div className="notice-card" role="note">
      <p className="notice-title">{title}</p>
      <p>
        Each message sends the problem statement, the code in your editor, and this chat to OpenAI to
        generate a reply — never your login or account details.
      </p>
      <p>
        Under OpenAI&rsquo;s data-sharing program, OpenAI may use that content to train and improve its
        models. Don&rsquo;t include passwords, personal information, or anything confidential.
      </p>
      <p>By sending a message you confirm you&rsquo;re 13 or older and agree to this.</p>
    </div>
  );
}
