#!/usr/bin/env perl
# Riscrive le tre funzioni find_button / find_dropdown / find_dropdown_selection
# in Transceiver/HRDTransceiver.cpp sostituendo gli overload QStringList::indexOf(QRegExp)
# / lastIndexOf(QRegExp) (rimossi in Qt6) con un ciclo esplicito basato su
# QRegularExpression::match().hasMatch().
#
# Uso: perl fix_hrd_transceiver.pl Transceiver/HRDTransceiver.cpp

use strict;
use warnings;

my $file = shift @ARGV or die "Usage: $0 <file>\n";

local $/;
open my $fh, '<', $file or die "Cannot open $file: $!\n";
my $content = <$fh>;
close $fh;

my $new = <<'NEW';
int HRDTransceiver::find_button (QRegularExpression const& re) const
{
  for (int i = 0; i < buttons_.size (); ++i)
    {
      if (re.match (buttons_.at (i)).hasMatch ())
        {
          return i;
        }
    }
  return -1;
}

int HRDTransceiver::find_dropdown (QRegularExpression const& re) const
{
  for (int i = 0; i < dropdown_names_.size (); ++i)
    {
      if (re.match (dropdown_names_.at (i)).hasMatch ())
        {
          return i;
        }
    }
  return -1;
}

std::vector<int> HRDTransceiver::find_dropdown_selection (int dropdown, QRegularExpression const& re) const
{
  std::vector<int> indices;
  auto list = dropdowns_.value (dropdown_names_.value (dropdown));
  // search backwards because more specialized modes tend to be
  // later in list
  for (int index = list.size () - 1; index >= 0; --index)
    {
      if (re.match (list.at (index)).hasMatch ())
        {
          indices.push_back (index);
        }
    }
  return indices;
}
NEW

my $pattern = qr/int HRDTransceiver::find_button.*?(?=void HRDTransceiver::map_modes)/s;

unless ($content =~ $pattern) {
  die "Pattern originale non trovato in $file - impossibile individuare il blocco da find_button a map_modes.\n";
}

$content =~ s/$pattern/$new\n/;

open my $out, '>', $file or die "Cannot write $file: $!\n";
print $out $content;
close $out;

print "Fatto: funzioni riscritte in $file\n";
