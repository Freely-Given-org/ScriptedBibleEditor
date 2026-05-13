// Scripted Bible Editor - A tool for applying scripted edits to ESFM and USFM files based on TSV command tables.
// Converted from Python to Rust by Gemini AI, May 2026 by RJH.

use anyhow::{anyhow, Result};
use clap::Parser;
use indexmap::IndexMap;
use serde::Deserialize;
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

use bos_books_codes::get_all_bos_book_codes;

const PROGRAM_NAME: &str = "Scripted Bible Editor";
const PROGRAM_VERSION: &str = "0.35-rust";
const SHORT_PROGRAM_NAME: &str = "ScriptedBibleEditor";

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Path to ScriptedBibleEditor.control.toml
    control_path: PathBuf,

    /// Flag where replacements were made
    #[arg(short, long)]
    flag: bool,

    /// Output less information to the console
    #[arg(short, long)]
    quiet: bool,

    /// Output no information to the console
    #[arg(short, long)]
    silent: bool,

    /// Output more information to the console
    #[arg(short, long)]
    informative: bool,

    /// Output lots of information for the user
    #[arg(short, long)]
    verbose: bool,

    /// Log errors to console
    #[arg(short, long)]
    errors: bool,

    /// Log warnings and errors to console
    #[arg(short, long)]
    warnings: bool,

    /// Output even more information for the programmer/debugger
    #[arg(short, long)]
    debug: bool,
}

#[derive(Debug, Deserialize)]
struct ControlData {
    title: Option<String>,
    #[serde(rename = "inputFolder")]
    input_folder: String,
    #[serde(rename = "inputFilenameTemplate")]
    input_filename_template: String,
    #[serde(rename = "outputFolder")]
    output_folder: String,
    #[serde(rename = "outputFilenameTemplate")]
    output_filename_template: Option<String>,
    #[serde(rename = "clearOutputFolder")]
    clear_output_folder: bool,
    #[serde(rename = "createOutputFolder")]
    create_output_folder: bool,
    #[serde(rename = "applyOrder")]
    _apply_order: Option<String>,
    #[serde(rename = "commandTables")]
    command_tables: IndexMap<String, String>,
}

#[derive(Debug, Clone)]
struct EditCommand {
    tags: String,
    i_books: Vec<String>,
    e_books: Vec<String>,
    i_markers: Vec<String>,
    e_markers: Vec<String>,
    i_refs: Vec<String>,
    e_refs: Vec<String>,
    pre_text: String,
    _s_case: String,
    search_text: String,
    post_text: String,
    _r_case: String,
    replace_text: String,
    _name: String,
    _comment: String,
}

struct State {
    control_data: ControlData,
    control_folderpath: PathBuf,
    command_tables: IndexMap<String, Vec<EditCommand>>,
    flag_replacements: bool,
    verbose: u8,
}

fn main() -> Result<()> {
    let args = Args::parse();
    
    let mut verbose = 2; // Default
    if args.silent { verbose = 0; }
    else if args.quiet { verbose = 1; }
    else if args.informative { verbose = 3; }
    else if args.verbose { verbose = 4; }
    if args.debug { verbose = 5; }

    if verbose > 1 {
        println!("{} v{}", PROGRAM_NAME, PROGRAM_VERSION);
    }

    let control_filepath = if args.control_path.is_dir() {
        args.control_path.join(format!("{}.control.toml", SHORT_PROGRAM_NAME))
    } else {
        args.control_path.clone()
    };

    if !control_filepath.exists() {
        return Err(anyhow!("No control file found at {:?}", control_filepath));
    }

    let control_folderpath = control_filepath.parent().unwrap().to_path_buf();
    let control_content = fs::read_to_string(&control_filepath)?;
    let control_data: ControlData = toml::from_str(&control_content)?;

    if verbose > 1 {
        println!("  Loading TOML control file at {:?}...", control_filepath);
        if let Some(title) = &control_data.title {
            println!("    Loaded parameters from '{}'.", title);
        }
    }

    let mut state = State {
        control_data,
        control_folderpath,
        command_tables: IndexMap::new(),
        flag_replacements: args.flag,
        verbose,
    };

    load_command_tables(&mut state)?;
    execute_edits_on_all_files(&state)?;

    if verbose > 1 {
        println!("{} v{} finished.", PROGRAM_NAME, PROGRAM_VERSION);
    }
    Ok(())
}

fn load_command_tables(state: &mut State) -> Result<()> {
    for (name, given_filepath) in &state.control_data.command_tables {
        let complete_filepath = state.control_folderpath.join(given_filepath);
        if state.verbose > 2 {
            println!("  Loading TSV command table file: {:?}...", complete_filepath);
        }

        let mut commands = Vec::new();
        let file = fs::File::open(&complete_filepath)?;
        let reader = std::io::BufReader::new(file);
        use std::io::BufRead;

        for (line_num, line_result) in reader.lines().enumerate() {
            let line_num = line_num + 1;
            let line = line_result?;
            let line_trimmed = line.trim_end_matches(['\r', '\n']);
            
            if line_trimmed.is_empty() || line_trimmed.starts_with('#') {
                continue;
            }

            if line_trimmed.starts_with("Tags\t") {
                continue;
            }

            let mut fields: Vec<String> = line_trimmed.split('\t').map(|s| s.to_string()).collect();
            
            // Handle cases where some columns were stripped
            if fields.len() > 9 && fields.len() < 15 {
                while fields.len() < 15 {
                    fields.push(String::new());
                }
            }

            if fields.len() < 15 {
                if state.verbose > 0 {
                    eprintln!("Skipping '{}' line {} which contains {} columns (expected 15)", name, line_num, fields.len());
                }
                continue;
            }

            let tags = fields[0].clone();
            let i_books = fields[1].split(',').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect::<Vec<_>>();
            let e_books = fields[2].split(',').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect::<Vec<_>>();
            let i_markers = fields[3].split(',').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect::<Vec<_>>();
            let e_markers = fields[4].split(',').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect::<Vec<_>>();
            let mut i_refs = fields[5].split(',').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect::<Vec<_>>();
            let mut e_refs = fields[6].split(',').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect::<Vec<_>>();

            // Validate and expand refs
            expand_refs(&mut i_refs)?;
            expand_refs(&mut e_refs)?;

            let mut replace_text = fields[12].clone();
            let search_text = fields[9].clone();

            // Transliteration (H and G tags)
            if tags.contains('H') {
                let capitalize = search_text.chars().next().map(|c| c.is_uppercase()).unwrap_or(false);
                let new_replace_text = bible_transliterations::transliterate_hebrew(&replace_text, capitalize);
                if new_replace_text != replace_text {
                    replace_text = if state.flag_replacements {
                        format!("H‹{}›H", new_replace_text)
                    } else {
                        new_replace_text
                    };
                }
                
                // Check for leftovers (excluding indicators if present)
                let check_text = replace_text.strip_prefix("H‹").and_then(|s| s.strip_suffix("›H")).unwrap_or(&replace_text);
                for c in check_text.chars() {
                    if bible_transliterations::is_hebrew(c) {
                        if state.verbose > 0 {
                            eprintln!("Critical: Have some Hebrew left-overs in '{}'", replace_text);
                        }
                        break;
                    }
                }
            }
            if tags.contains('G') {
                let new_replace_text = bible_transliterations::transliterate_greek(&replace_text);
                if new_replace_text != replace_text {
                    replace_text = if state.flag_replacements {
                        format!("G‹{}›G", new_replace_text)
                    } else {
                        new_replace_text
                    };
                }
                
                let check_text = replace_text.strip_prefix("G‹").and_then(|s| s.strip_suffix("›G")).unwrap_or(&replace_text);
                for c in check_text.chars() {
                    if bible_transliterations::is_greek(c) {
                        if state.verbose > 0 {
                            eprintln!("Critical: Have some Greek left-overs in '{}'", replace_text);
                        }
                        break;
                    }
                }
            }

            commands.push(EditCommand {
                tags,
                i_books,
                e_books,
                i_markers,
                e_markers,
                i_refs,
                e_refs,
                pre_text: fields[7].clone(),
                _s_case: fields[8].clone(),
                search_text: fields[9].clone(),
                post_text: fields[10].clone(),
                _r_case: fields[11].clone(),
                replace_text,
                _name: fields[13].clone(),
                _comment: fields[14].clone(),
            });
        }
        if state.verbose > 1 {
            println!("      Loaded {} commands for '{}' TSV.", commands.len(), name);
        }
        state.command_tables.insert(name.clone(), commands);
    }
    Ok(())
}

fn expand_refs(refs: &mut Vec<String>) -> Result<()> {
    let mut expanded = Vec::new();
    for r in refs.iter() {
        if r.contains('_') && !r.contains(':') {
            let bits: Vec<&str> = r.split('_').collect();
            if bits.len() == 2 {
                let book = bits[0];
                if bits[1].parse::<u32>().is_ok() {
                    for v in 1..=150 {
                        expanded.push(format!("{}_{}:{}", book, bits[1], v));
                    }
                }
            }
        }
    }
    refs.extend(expanded);
    Ok(())
}

fn execute_edits_on_all_files(state: &State) -> Result<()> {
    let input_folder = state.control_folderpath.join(&state.control_data.input_folder);
    let output_folder = state.control_folderpath.join(&state.control_data.output_folder);

    if !input_folder.is_dir() {
        return Err(anyhow!("Input folder {:?} is not a directory", input_folder));
    }

    if state.control_data.clear_output_folder {
        if output_folder.exists() {
            fs::remove_dir_all(&output_folder)?;
        }
    }
    if state.control_data.create_output_folder {
        if !output_folder.exists() {
            fs::create_dir_all(&output_folder)?;
        }
    }

    let mut num_files_written = 0;
    let mut esfm_filelist = HashSet::new();
    let abbreviations = get_all_bos_book_codes();

    for bbb in abbreviations {
        let uuu = bos_books_codes::bos_book_code_to_usfm_abbrev(&bbb).ok().flatten().unwrap_or("").to_uppercase();
        let input_filename = state.control_data.input_filename_template
            .replace("BBB", &bbb)
            .replace("UUU", &uuu);
        
        let output_filename = state.control_data.output_filename_template.as_ref()
            .map(|t| t.replace("BBB", &bbb).replace("UUU", &uuu))
            .unwrap_or_else(|| input_filename.clone());

        let input_filepath = input_folder.join(&input_filename);
        if input_filepath.is_file() {
            if state.verbose > 2 {
                println!("  Processing {}...", input_filename);
            }
            let input_text = fs::read_to_string(&input_filepath)?;
            
            extract_esfm_table_names(&input_filename, &input_text, &mut esfm_filelist);
            
            let applied_text = execute_edits(&bbb, &input_text, state)?;

            if applied_text != input_text {
                let mut final_text = applied_text;
                let rem_line = format!("\n\\rem USFM file edited by {} v{}\n\\h ", PROGRAM_NAME, PROGRAM_VERSION);
                final_text = final_text.replace("\n\\h ", &rem_line);

                let output_filepath = output_folder.join(&output_filename);
                fs::write(output_filepath, final_text)?;
                num_files_written += 1;
            }
        }
    }

    if !esfm_filelist.is_empty() {
        num_files_written += copy_auxiliary_esfm_files(&input_folder, &output_folder, &esfm_filelist, state)?;
    }

    if state.verbose > 1 {
        println!("  {} files written to {:?}", num_files_written, output_folder);
    }
    Ok(())
}

fn extract_esfm_table_names(filename: &str, file_text: &str, esfm_filelist: &mut HashSet<String>) {
    if filename.ends_with(".ESFM") || file_text.contains("\\rem ESFM v") {
        for table_type in &["WORKDATA", "FILEDATA", "WORDTABLE"] {
            let search_string = format!("\\rem {} ", table_type);
            if let Some(idx) = file_text.find(&search_string) {
                let start = idx + search_string.len();
                if let Some(end) = file_text[start..].find('\n') {
                    let table_filename = file_text[start..start + end].trim();
                    esfm_filelist.insert(table_filename.to_string());
                }
            }
        }
    }
}

fn copy_auxiliary_esfm_files(input_folder: &Path, output_folder: &Path, esfm_filelist: &HashSet<String>, state: &State) -> Result<usize> {
    let mut count = 0;
    for filename in esfm_filelist {
        let input_path = input_folder.join(filename);
        let output_path = output_folder.join(filename);
        if input_path.exists() {
            if state.verbose > 1 {
                println!("Copying ESFM auxiliary {:?} to {:?}...", input_path, output_path);
            }
            fs::copy(&input_path, &output_path)?;
            count += 1;
        }
    }
    Ok(count)
}

fn execute_edits(bbb: &str, input_text: &str, state: &State) -> Result<String> {
    let mut applied_text = input_text.to_string();
    for (name, commands) in &state.command_tables {
        if state.verbose > 2 {
            println!("    Applying {} commands from {}...", commands.len(), name);
        }
        applied_text = execute_edit_commands(bbb, &applied_text, commands, state)?;
    }
    Ok(applied_text)
}

fn execute_edit_commands(bbb: &str, input_text: &str, commands: &[EditCommand], state: &State) -> Result<String> {
    let mut adjusted_text = input_text.to_string();

    for command in commands {
        if !command.i_books.is_empty() && !command.i_books.contains(&bbb.to_string()) {
            continue;
        }
        if command.e_books.contains(&bbb.to_string()) {
            continue;
        }

        let is_regex = command.tags.contains('w') || !command.pre_text.is_empty() || !command.post_text.is_empty() || command.search_text.contains('¦');

        if command.i_markers.is_empty() && command.e_markers.is_empty() && command.i_refs.is_empty() && command.e_refs.is_empty() {
            if is_regex {
                adjusted_text = execute_regex_edit_chunk_command(bbb, &adjusted_text, command, state)?;
            } else {
                adjusted_text = execute_edit_chunk_command(bbb, &adjusted_text, command, state)?;
            }
        } else {
            let mut new_lines = Vec::new();
            let mut c = "-1".to_string();
            let mut v = "-1".to_string();
            let mut last_marker: Option<String> = None;

            for line in adjusted_text.lines() {
                if c == "-1" {
                    v = (v.parse::<i32>().unwrap_or(0) + 1).to_string();
                }
                
                let (marker, text) = split_usfm_marker_from_text(line);
                if let Some(ref m) = marker {
                    if m == "c" {
                        c = text.trim().to_string();
                        v = "0".to_string();
                    } else if m == "v" {
                        v = text.split_whitespace().next().unwrap_or("0").to_string();
                    }
                }

                let effective_marker = marker.clone().or(last_marker.clone());
                last_marker = marker.clone();

                let mut skip = false;
                if let Some(ref em) = effective_marker {
                    if command.e_markers.contains(em) {
                        skip = true;
                    } else if !command.i_markers.is_empty() && !command.i_markers.contains(em) {
                        skip = true;
                    }
                }

                if !skip {
                    let cv_ref = format!("{}:{}", c, v);
                    let bcv_ref = format!("{}_{}:{}", bbb, c, v);
                    if command.e_refs.contains(&cv_ref) || command.e_refs.contains(&bcv_ref) {
                        skip = true;
                    } else if !command.i_refs.is_empty() && !command.i_refs.contains(&cv_ref) && !command.i_refs.contains(&bcv_ref) {
                        skip = true;
                    }
                }

                if skip {
                    new_lines.push(line.to_string());
                } else {
                    let where_str = format!("{}_{}:{}~{:?}", bbb, c, v, marker);
                    if is_regex {
                        new_lines.push(execute_regex_edit_chunk_command(&where_str, line, command, state)?);
                    } else {
                        new_lines.push(execute_edit_chunk_command(&where_str, line, command, state)?);
                    }
                }
            }
            adjusted_text = new_lines.join("\n");
        }
    }
    Ok(adjusted_text)
}

fn split_usfm_marker_from_text(line: &str) -> (Option<String>, &str) {
    if line.is_empty() || !line.starts_with('\\') {
        return (None, line);
    }

    let line_after = &line[1..];
    let mut end_idx = line_after.len();
    for (i, c) in line_after.char_indices() {
        if c == ' ' || c == '*' || c == '\\' {
            end_idx = i;
            break;
        }
    }

    let marker = &line_after[..end_idx];
    let rest = &line_after[end_idx..];

    let text = if rest.starts_with(' ') {
        &rest[1..]
    } else {
        rest
    };

    (Some(marker.to_string()), text)
}

const STANDARD_DISTANCE: usize = 2500;

fn execute_edit_chunk_command(where_str: &str, input_text: &str, command: &EditCommand, state: &State) -> Result<String> {
    let search = &command.search_text;
    let replace = &command.replace_text;

    if input_text.contains(search) {
        if command.tags.contains('d') && input_text.len() > STANDARD_DISTANCE {
            let short_replace = if replace.contains('/') {
                replace.split('/').next().unwrap_or(replace).to_string()
            } else {
                let add_re = fancy_regex::Regex::new(r"\\add .+?\\add[*]").unwrap();
                add_re.replace_all(replace, "").to_string()
            };

            let mut result = String::with_capacity(input_text.len());
            let mut last_idx = 0;
            let mut last_full_char_idx: Option<usize> = None;
            
            // Map byte indices to character counts for distance calculation
            let char_indices: Vec<usize> = input_text.char_indices().map(|(i, _)| i).collect();
            let byte_to_char = |byte_idx: usize| {
                char_indices.iter().position(|&bi| bi == byte_idx).unwrap_or(char_indices.len())
            };

            for (idx, _) in input_text.match_indices(search) {
                result.push_str(&input_text[last_idx..idx]);
                
                let current_char_idx = byte_to_char(idx);
                let use_full = match last_full_char_idx {
                    None => true,
                    Some(prev) => (current_char_idx - prev) >= STANDARD_DISTANCE,
                };

                if use_full {
                    result.push_str(replace);
                    last_full_char_idx = Some(current_char_idx);
                } else {
                    result.push_str(&short_replace);
                }
                last_idx = idx + search.len();
            }
            result.push_str(&input_text[last_idx..]);
            return Ok(result);
        } else {
            let mut adjusted_text = input_text.replace(search, replace);
            if command.tags.contains('l') {
                let mut last_count = input_text.matches(search).count();
                loop {
                    let next_text = adjusted_text.replace(search, replace);
                    let new_count = next_text.matches(search).count();
                    if new_count >= last_count {
                        if new_count > 0 && state.verbose > 0 {
                            eprintln!("Critical: Aborted endless loop replacing '{}' with '{}' in {}", search, replace, where_str);
                        }
                        break;
                    }
                    adjusted_text = next_text;
                    last_count = new_count;
                    if last_count == 0 { break; }
                }
            }
            return Ok(adjusted_text);
        }
    }
    Ok(input_text.to_string())
}

fn execute_regex_edit_chunk_command(where_str: &str, input_text: &str, command: &EditCommand, state: &State) -> Result<String> {
    let search_text = &command.search_text;
    let search_broken_pipe_count = search_text.matches('¦').count();
    let mut search_pattern = escape_usfm_regex(search_text);

    if search_broken_pipe_count > 0 {
        search_pattern = search_pattern.replace('¦', r"(¦[1-9][0-9]{0,5})");
    }
    
    let mut pattern = format!("({})", search_pattern);
    
    if !command.pre_text.is_empty() {
        pattern = format!(r"(?{}){}", escape_usfm_regex(&command.pre_text), pattern);
    } else if command.tags.contains('w') {
        pattern = format!(r"(?:\b|(?<=_)){}", pattern);
    }

    if !command.post_text.is_empty() {
        pattern = format!(r"{}(?{})", pattern, escape_usfm_regex(&command.post_text));
    } else if command.tags.contains('w') {
        pattern = format!(r"{}\b", pattern);
    }

    let re = fancy_regex::RegexBuilder::new(&pattern)
        .backtrack_limit(100_000_000)
        .build()
        .map_err(|e| anyhow!("Invalid regex pattern '{}': {}", pattern, e))?;
    
    let original_replace_text = if state.flag_replacements {
        format!("Rx-{}Rx", command.replace_text)
    } else {
        command.replace_text.clone()
    };

    let mut result = String::with_capacity(input_text.len());
    let mut last_end = 0;

    for caps_result in re.captures_iter(input_text) {
        let caps = caps_result.map_err(|e| anyhow!("Regex execution error at {}: {}", where_str, e))?;
        let m = caps.get(0).ok_or_else(|| anyhow!("Failed to get match for pattern '{}'", pattern))?;
        
        result.push_str(&input_text[last_end..m.start()]);
        
        if search_broken_pipe_count > 0 {
            let mut final_replace = original_replace_text.clone();
            
            // Extract all captured word-link numbers
            let mut wl_nums = Vec::new();
            // The first capture group is the outer one we added.
            // Subsequent groups come from search_pattern.replace('¦', r"(¦...)")
            for i in 2..caps.len() {
                if let Some(wl_match) = caps.get(i) {
                    let wl_str = wl_match.as_str();
                    if wl_str.starts_with('¦') {
                        wl_nums.push(wl_str);
                    }
                }
            }

            if !wl_nums.is_empty() && final_replace.contains('¦') {
                if search_broken_pipe_count == 1 {
                    final_replace = final_replace.replace('¦', wl_nums[0]);
                } else {
                    // Sequential replacement of ¦ placeholders
                    for num in wl_nums {
                        if let Some(pos) = final_replace.find('¦') {
                            final_replace.replace_range(pos..pos+'¦'.len_utf8(), num);
                        }
                    }
                }
            }
            result.push_str(&final_replace);
        } else {
            result.push_str(&original_replace_text);
        }
        
        last_end = m.end();
    }
    result.push_str(&input_text[last_end..]);

    Ok(result)
}

fn escape_usfm_regex(text: &str) -> String {
    text.replace('\\', "\\\\")
        .replace('*', r"[*]")
        .replace('+', r"[+]")
        .replace('(', r"[(]")
        .replace(')', r"[)]")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hag_transliteration() -> Result<()> {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let test_files_dir = root.join("../../../ScriptedBibleEditor/TestFiles").canonicalize()?;
        let control_path = test_files_dir.join("ScriptedOTUpdates/ScriptedBibleEditor.control.toml");
        
        let control_content = fs::read_to_string(&control_path)?;
        let mut control_data: ControlData = toml::from_str(&control_content)?;
        
        // Ensure output folder exists
        let output_folder = test_files_dir.join("newTestOutput");
        if !output_folder.exists() {
            fs::create_dir_all(&output_folder)?;
        }
        
        // Override control data to point to the correct test files
        control_data.input_folder = "../".to_string();
        control_data.output_folder = "../newTestOutput/".to_string();
        
        let mut state = State {
            control_data,
            control_folderpath: control_path.parent().unwrap().to_path_buf(),
            command_tables: IndexMap::new(),
            flag_replacements: false,
            verbose: 0,
        };

        load_command_tables(&mut state)?;
        execute_edits_on_all_files(&state)?;
        
        let actual_path = output_folder.join("OET-LV_HAG.ESFM");
        let actual_content = fs::read_to_string(actual_path)?;
        
        let expected_path = test_files_dir.join("OET-LV_HAG.ESFM");
        let expected_content = fs::read_to_string(expected_path)?;
        
        let actual_lines: Vec<&str> = actual_content.lines().collect();
        let expected_lines: Vec<&str> = expected_content.lines().collect();
        
        // Compare lines, ignoring line 9 (version number)
        for (i, (actual, expected)) in actual_lines.iter().zip(expected_lines.iter()).enumerate() {
            let line_num = i + 1;
            if line_num == 9 { continue; }
            
            assert_eq!(actual.trim(), expected.trim(), "Mismatch at line {}", line_num);
        }
        
        assert_eq!(actual_lines.len(), expected_lines.len(), "File length mismatch");
        
        Ok(())
    }
}
