import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Home,
  FolderKanban,
  Search,
  Share2,
} from 'lucide-react';

const navigation = [
  { name: '仪表盘', href: '/', icon: Home },
  { name: '知识库', href: '/collections', icon: FolderKanban },
  { name: '搜索', href: '/search', icon: Search },
  { name: '分享管理', href: '/shares', icon: Share2 },
];

export default function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0">
      <div className="flex flex-col flex-grow border-r bg-muted/40 pt-14 overflow-y-auto">
        <nav className="flex-1 px-2 py-4 space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              end={item.href === '/'}
              className={({ isActive }) =>
                cn(
                  'group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )
              }
            >
              <item.icon
                className="mr-3 flex-shrink-0 h-5 w-5"
                aria-hidden="true"
              />
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  );
}


