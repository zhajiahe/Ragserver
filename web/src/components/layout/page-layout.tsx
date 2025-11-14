import { ReactNode } from 'react';

interface PageLayoutProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}

export default function PageLayout({ title, description, action, children }: PageLayoutProps) {
  return (
    <div className="flex-1">
      {(title || action) && (
        <div className="border-b">
          <div className="flex h-16 items-center px-4 md:px-6">
            <div className="flex-1">
              {title && <h1 className="text-2xl font-bold tracking-tight">{title}</h1>}
              {description && (
                <p className="text-sm text-muted-foreground mt-1">{description}</p>
              )}
            </div>
            {action && <div>{action}</div>}
          </div>
        </div>
      )}
      <div className="p-4 md:p-6">{children}</div>
    </div>
  );
}


