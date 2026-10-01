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
 * and using the extension is the agreeing act. It is also reachable at any
 * time from the Privacy link in the header. See docs/design-choices.md.
 *
 * "Using", not "sending a message": accepted submissions are summarised and
 * saved without the user typing anything. That only happens while the panel
 * is open, which is where this notice is shown.
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
        When LeetCode accepts a submission, or you open one it accepted earlier, the accepted code is
        also sent to OpenAI to write a short summary, and the code and summary are saved to your account.
      </p>
      <p>
        Under OpenAI&rsquo;s data-sharing program, OpenAI may use that content to train and improve its
        models. Don&rsquo;t include passwords, personal information, or anything confidential.
      </p>
      <p>By using LeetCode AUX you confirm you&rsquo;re 13 or older and agree to this.</p>
    </div>
  );
}
