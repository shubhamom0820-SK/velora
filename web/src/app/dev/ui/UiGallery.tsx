"use client";

import {
  Bell,
  CircleAlert,
  Heart,
  Inbox,
  MapPin,
  Sparkles,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { ButtonLink } from "@/components/ui/ButtonLink";
import { Chip } from "@/components/ui/Chip";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { OtpInput } from "@/components/ui/OtpInput";
import { PinPad } from "@/components/ui/PinPad";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { TextArea } from "@/components/ui/TextArea";
import { Toggle } from "@/components/ui/Toggle";
import { useToast } from "@/components/ui/useToast";

// A 1×1 PNG, so the photo state renders without a network request.
const PHOTO =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

const INTERESTS = ["Filter coffee", "Trekking", "Indie music"];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-title-2 text-ink">{title}</h2>
      {children}
    </section>
  );
}

function Row({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>;
}

export function UiGallery() {
  const toast = useToast();
  const [verifiedOnly, setVerifiedOnly] = useState(true);
  const [onlineNow, setOnlineNow] = useState(false);
  const [picked, setPicked] = useState(INTERESTS);
  const [matches, setMatches] = useState(true);
  const [messages, setMessages] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [pin, setPin] = useState("");
  const [otp, setOtp] = useState("");
  const [chromePin, setChromePin] = useState("48");

  return (
    <main className="bg-bg mx-auto flex min-h-dvh max-w-130 flex-col gap-10 px-5 py-8 md:px-6">
      <header>
        <h1 className="text-title-1 text-ink">UI primitives</h1>
        <p className="text-small text-mute">
          src/components/ui — every primitive in every state. Dev only.
        </p>
      </header>

      <Section title="Button">
        <Row>
          <Button>Primary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
        </Row>
        <Row>
          <Button size="sm">Primary sm</Button>
          <Button size="sm" variant="ghost">
            Ghost sm
          </Button>
          <Button size="sm" variant="danger">
            Danger sm
          </Button>
        </Row>
        <Row>
          <Button disabled>Disabled</Button>
          <Button variant="ghost" disabled>
            Disabled
          </Button>
          <Button variant="danger" disabled>
            Disabled
          </Button>
        </Row>
        <Row>
          <Button loading>Loading</Button>
          <Button variant="ghost" size="sm" loading>
            Loading
          </Button>
        </Row>
        <Button fullWidth>
          <Icon icon={Heart} size={18} /> Full width with icon
        </Button>
        <div className="bg-chrome rounded-card flex flex-wrap gap-3 p-4">
          <Button>Primary on chrome</Button>
          <Button variant="chrome">Chrome</Button>
          <Button variant="chrome" size="sm">
            Chrome sm
          </Button>
          <Button variant="chrome" disabled>
            Disabled
          </Button>
        </div>
      </Section>

      <Section title="ButtonLink">
        <Row>
          <ButtonLink href="/dev/ui">Primary link</ButtonLink>
          <ButtonLink href="/dev/ui" variant="ghost" size="sm">
            Ghost sm link
          </ButtonLink>
        </Row>
        <div className="bg-chrome rounded-card flex flex-wrap gap-3 p-4">
          <ButtonLink href="/dev/ui" size="sm">
            Primary sm on chrome
          </ButtonLink>
          <ButtonLink href="/dev/ui" variant="chrome">
            Chrome link
          </ButtonLink>
        </div>
      </Section>

      <Section title="Chip">
        <Row>
          <Chip
            active={verifiedOnly}
            onClick={() => setVerifiedOnly(!verifiedOnly)}
          >
            Selfie matched only
          </Chip>
          <Chip
            icon={Sparkles}
            active={onlineNow}
            onClick={() => setOnlineNow(!onlineNow)}
          >
            Online now
          </Chip>
          <Chip onClick={() => toast.show({ message: "Plain chip" })}>
            Plain
          </Chip>
          <Chip disabled>Disabled</Chip>
        </Row>
        <Row>
          {picked.map((label) => (
            <Chip
              key={label}
              onRemove={() => setPicked(picked.filter((p) => p !== label))}
            >
              {label}
            </Chip>
          ))}
          {picked.length < INTERESTS.length && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPicked(INTERESTS)}
            >
              Reset
            </Button>
          )}
        </Row>
      </Section>

      <Section title="Field">
        <Field label="First name" placeholder="As it should appear" />
        <Field label="Username" helper="Letters, numbers and dots" />
        <Field
          label="Username"
          defaultValue="ananya"
          error="That username is taken"
        />
        <Field label="Phone" defaultValue="+91 98xxx xxxxx" disabled />
      </Section>

      <Section title="TextArea">
        <TextArea
          label="About you"
          maxLength={300}
          placeholder="A line or two"
        />
        <TextArea
          label="What happened?"
          helper="Only our moderators see this"
          error="Tell us a little more"
          maxLength={500}
        />
      </Section>

      <Section title="OtpInput">
        <div className="flex max-w-90 flex-col gap-4">
          <OtpInput label="Code" value={otp} onChange={setOtp} />
          <OtpInput
            label="Wrong code"
            value="12345"
            onChange={() => {}}
            invalid
          />
          <OtpInput
            label="Checking"
            value="123456"
            onChange={() => {}}
            disabled
          />
        </div>
      </Section>

      <Section title="PinPad">
        <Row>
          <PinPad
            value={pin}
            onChange={setPin}
            onComplete={() => toast.show({ message: "PIN entered" })}
          />
          <div className="bg-chrome rounded-card p-6">
            <PinPad
              tone="chrome"
              value={chromePin}
              onChange={setChromePin}
              onComplete={() => {}}
            />
          </div>
          <PinPad
            value="12"
            onChange={() => {}}
            onComplete={() => {}}
            disabled
          />
        </Row>
      </Section>

      <Section title="Toggle">
        <div className="flex flex-col">
          <Toggle label="New match" checked={matches} onChange={setMatches} />
          <Toggle
            label="New message"
            description="Only the name, never the text"
            checked={messages}
            onChange={setMessages}
          />
          <Toggle label="Disabled on" checked disabled onChange={() => {}} />
          <Toggle
            label="Disabled off"
            checked={false}
            disabled
            onChange={() => {}}
          />
        </div>
      </Section>

      <Section title="Avatar">
        <Row>
          <Avatar name="Ananya" src={PHOTO} />
          <Avatar name="Meera" />
          <Avatar name="Ishita" online />
          <Avatar name="Kabir" verified />
          <Avatar name="Dev" size={50} online verified />
        </Row>
      </Section>

      <Section title="Icon">
        <Row>
          <Icon icon={Heart} />
          <Icon icon={MapPin} size={16} />
          <Icon icon={Bell} size={22} label="Notifications" />
          <Icon icon={CircleAlert} className="text-accent" />
        </Row>
      </Section>

      <Section title="Spinner and Skeleton">
        <Row>
          <Spinner />
          <Spinner size={28} label="Loading chats" className="text-accent" />
        </Row>
        <div className="flex items-center gap-3">
          <Skeleton variant="avatar" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton />
            <Skeleton className="w-2/3" />
          </div>
        </div>
        <Skeleton variant="card" />
      </Section>

      <Section title="EmptyState and ErrorState">
        <div className="rounded-card border-line border">
          <EmptyState
            icon={Inbox}
            title="Nobody matches that"
            body="Try clearing your search or filters."
            action={{
              label: "Clear everything",
              onClick: () => toast.show({ message: "Cleared" }),
            }}
          />
        </div>
        <div className="rounded-card border-line border">
          <EmptyState title="Nothing yet" />
        </div>
        <div className="rounded-card border-line border">
          <ErrorState
            onRetry={() => toast.show({ message: "Retrying", tone: "error" })}
          />
        </div>
      </Section>

      <Section title="Toast">
        <Row>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => toast.show({ message: "Link copied" })}
          >
            Info
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              toast.show({ message: "Payment failed", tone: "error" })
            }
          >
            Error
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              toast.show({
                message: "Cleared from your chats",
                action: {
                  label: "Undo",
                  onClick: () => toast.show({ message: "Restored" }),
                },
              })
            }
          >
            With Undo
          </Button>
        </Row>
      </Section>

      <Section title="Sheet">
        <Button variant="ghost" onClick={() => setSheetOpen(true)}>
          Open a sheet
        </Button>
        <Sheet
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          title="Report Ananya"
          footer={
            <div className="flex flex-col gap-2">
              <Button fullWidth onClick={() => setSheetOpen(false)}>
                Send report
              </Button>
              <Button
                variant="ghost"
                fullWidth
                onClick={() => setSheetOpen(false)}
              >
                Cancel
              </Button>
            </div>
          }
        >
          <div className="flex flex-col gap-4">
            <Row>
              <Chip active>Fake profile</Chip>
              <Chip active={false}>Asking for money</Chip>
            </Row>
            <TextArea label="What happened?" maxLength={500} />
            {Array.from({ length: 8 }, (_, i) => (
              <p key={i} className="text-body text-mute">
                Scroll filler {i + 1}: the body scrolls while the title and the
                footer stay put.
              </p>
            ))}
          </div>
        </Sheet>
      </Section>
    </main>
  );
}
