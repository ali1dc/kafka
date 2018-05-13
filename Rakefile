# frozen_string_literal: true

$LOAD_PATH << './pipeline/lib'
# require 'json'
# require 'erb'

# Load any .rake files under the current directory
Dir.glob('**/*.rake').each do |task_file|
  load task_file
end

# system('bundle', 'install', '--quiet')

# Dir.glob(File.join('**/*.rake')).each { |file| load file }

begin
  require 'rspec/core/rake_task'
  RSpec::Core::RakeTask.new(:spec)
rescue LoadError
  print "Unable to load rspec/core/rake_task, spec tests missing\n"
end

begin
  require 'rubocop/rake_task'
  RuboCop::RakeTask.new(:rubocop)
rescue LoadError
  print "Unable to load rubocop/rake_task, rubocop tests missing\n"
end
